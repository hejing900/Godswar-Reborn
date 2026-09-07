using Godswar.Server.Domain.World.Content;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    private async Task<bool> TryHandleCapitalNpcDialogOpenAsync(
        NpcSpawnDefinition npc,
        CancellationToken cancellationToken)
    {
        if (!CapitalNpcServiceProtocol.TryResolve(npc, out var service) ||
            service == CapitalNpcServiceKind.ExchangeMentor)
        {
            return false;
        }

        byte[] packet;
        if (service == CapitalNpcServiceKind.TeachingManager)
        {
            packet = PacketBuilder.NpcDescriptionDialogOpenAck(
                npc.InteractionId,
                npc.NpcKey);
        }
        else if (CapitalNpcServiceProtocol.IsShop(service))
        {
            packet = PacketBuilder.NpcShopDialogOpenAck(
                npc.InteractionId,
                npc.NpcKey);
        }
        else if (service == CapitalNpcServiceKind.PrizeChest)
        {
            packet = PacketBuilder.NpcPrizeChestDialogOpenAck(
                npc.InteractionId,
                npc.NpcKey);
        }
        else if (CapitalNpcServiceProtocol.TryGetDialogueRoutes(
                     npc,
                     out var routes))
        {
            packet = PacketBuilder.NpcDialogOpenAck(
                npc.InteractionId,
                routes[0].DialogIndex,
                npc.NpcKey);
        }
        else
        {
            return false;
        }
        await _session.SendAsync(
            packet,
            cancellationToken,
            "CapitalNpcDialogOpenAck");
        Console.WriteLine(
            $"[npc] capital open npc={npc.InteractionId} " +
            $"key={npc.NpcKey} service={service}");
        return true;
    }

    private async Task<bool> TryHandleCapitalNpcPageRequestAsync(
        NpcSpawnDefinition npc,
        CancellationToken cancellationToken)
    {
        if (!CapitalNpcServiceProtocol.TryResolve(npc, out var service))
        {
            return false;
        }

        if (CapitalNpcServiceProtocol.IsShop(service))
        {
            await _session.SendAsync(
                PacketBuilder.CapitalNpcShopCatalog(
                    npc.InteractionId,
                    GetCapitalShopBalances(),
                    service),
                cancellationToken,
                "NpcShopCatalog",
                framed: false);
        }

        return true;
    }

    private async Task HandleCapitalNpcCreditExchangeAsync(
        uint npcId,
        int dialogIndex,
        int subId,
        CancellationToken cancellationToken)
    {
        if (dialogIndex != CapitalNpcServiceProtocol.ExchangeDialogIndex)
        {
            return;
        }

        if (CapitalNpcServiceProtocol.TryGetExchangePage(
                subId,
                out var pageSubIds))
        {
            await _session.SendAsync(
                PacketBuilder.NpcFunctionActionResponse(
                    npcId,
                    dialogIndex,
                    pageSubIds),
                cancellationToken,
                "NpcFunctionActionResponse");
            return;
        }

        // The browse capture did not include a confirmed exchange. Consume
        // those mutation attempts without inventing balances or rewards.
        if (subId is >= 311 and <= 316)
        {
            Console.WriteLine(
                $"[npc] credit exchange confirmation unavailable " +
                $"npc={npcId} subId={subId}");
        }
    }

    private async Task HandleCapitalNpcShopPurchaseAsync(
        GamePacket packet,
        CancellationToken cancellationToken)
    {
        if (_account is null || _character is null ||
            !CapitalNpcServiceProtocol.TryParsePurchase(
                packet.Payload,
                out var intent) ||
            !TryResolveMapNpc(intent.NpcId, out var npc) ||
            !CapitalNpcServiceProtocol.TryResolve(npc, out var service) ||
            !CapitalNpcServiceProtocol.IsShop(service) ||
            !PacketBuilder.TryResolveCapitalNpcShopOffer(
                service,
                intent.Category,
                intent.ListingIndex,
                intent.ItemId,
                out var offer))
        {
            Console.Error.WriteLine(
                "[npc-shop] rejected malformed or untrusted purchase " +
                $"length={packet.Length}");
            return;
        }

        var result = await _store.PurchaseCapitalShopItemAsync(
            _account.Id,
            _character.Id,
            Guid.NewGuid(),
            offer,
            intent.Quantity,
            cancellationToken);
        if (!result.Purchased || result.Character is null)
        {
            Console.WriteLine(
                $"[npc-shop] purchase rejected character={_character.Name} " +
                $"npc={intent.NpcId} item={intent.ItemId} " +
                $"quantity={intent.Quantity} status={result.Status}");
            await SendCapitalShopCatalogAsync(
                npc,
                service,
                result.Status is
                    CapitalShopPurchaseStatus.InsufficientCurrency or
                    CapitalShopPurchaseStatus.InsufficientCapacity
                    ? GetCapitalShopBalances(
                        offer.Currency,
                        result.CurrencyBalance)
                    : GetCapitalShopBalances(),
                cancellationToken);
            return;
        }

        InstallCapitalShopProjection(result.Character);
        _registry.UpdateCharacter(
            _session,
            _character,
            advanceWorldRevision: false);
        await _session.SendAsync(
            BuildLocalPlayerStatusUpdate(),
            cancellationToken,
            "NpcShopWalletStatus");
        await SendKitBagRefreshAsync(cancellationToken);
        await SendCapitalShopCatalogAsync(
            npc,
            service,
            GetCapitalShopBalances(),
            cancellationToken);
        Console.WriteLine(
            $"[npc-shop] purchased character={_character.Name} " +
            $"npc={intent.NpcId} item={intent.ItemId} " +
            $"quantity={intent.Quantity} unitPrice={offer.UnitPrice} " +
            $"currency={offer.Currency} " +
            $"balance={GetCapitalShopCurrencyBalance(offer.Currency)}");
    }

    private void InstallCapitalShopProjection(GameCharacter updated)
    {
        if (_character is null ||
            updated.Id != _character.Id ||
            updated.AccountId != _character.AccountId ||
            updated.RealmId != _character.RealmId)
        {
            throw new InvalidDataException(
                "The purchased shop projection has the wrong owner.");
        }

        // A shop purchase changes only the wallet and kit bag. The legacy
        // character reload contains stored base HP/MP, not the live derived
        // equipment projection, so replacing the whole character would clamp
        // the authoritative live vitals to those base values.
        _character.Silver = updated.Silver;
        _character.Gold = updated.Gold;
        _character.BindingGold = updated.BindingGold;
        _character.KitBag = updated.KitBag;
    }

    private int GetCapitalShopCurrencyBalance(
        CapitalNpcShopCurrency currency)
    {
        if (_character is null)
        {
            return 0;
        }
        return currency switch
        {
            CapitalNpcShopCurrency.Silver => _character.Silver,
            CapitalNpcShopCurrency.Gold => _character.Gold,
            CapitalNpcShopCurrency.BindingGold => _character.BindingGold,
            _ => 0
        };
    }

    private CapitalNpcShopBalances GetCapitalShopBalances(
        CapitalNpcShopCurrency? overrideCurrency = null,
        int overrideBalance = 0)
    {
        var balances = _character is null
            ? default
            : new CapitalNpcShopBalances(
                _character.Silver,
                _character.Gold,
                _character.BindingGold);
        if (!overrideCurrency.HasValue)
        {
            return balances;
        }

        var balance = Math.Max(0, overrideBalance);
        return overrideCurrency.Value switch
        {
            CapitalNpcShopCurrency.Silver => balances with
            {
                Silver = balance
            },
            CapitalNpcShopCurrency.Gold => balances with
            {
                Gold = balance
            },
            CapitalNpcShopCurrency.BindingGold => balances with
            {
                BindingGold = balance
            },
            _ => balances
        };
    }

    private Task SendCapitalShopCatalogAsync(
        NpcSpawnDefinition npc,
        CapitalNpcServiceKind service,
        CapitalNpcShopBalances balances,
        CancellationToken cancellationToken) =>
        _session.SendAsync(
            PacketBuilder.CapitalNpcShopCatalog(
                npc.InteractionId,
                balances,
                service),
            cancellationToken,
            "NpcShopCatalogRefresh",
            framed: false);
}
