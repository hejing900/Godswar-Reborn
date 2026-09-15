using System.Buffers.Binary;
using System.Text;
using Godswar.Server.Application.Accounts;
using Godswar.Server.Application.Characters;
using Godswar.Server.Application.Inventory;
using Godswar.Server.Application.Pets;
using Godswar.Server.Application.Talents;
using Godswar.Server.Application.World;
using Godswar.Server.Application.Zodiac;
using Godswar.Server.Networking;
using Godswar.Server.Networking.Secure.Udp;
using Godswar.Server.Operations;
using Godswar.Server.Operations.Observability;
using Godswar.Server.Packets;
using Godswar.Server.Protocol;
using Godswar.Server.State;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler : IClientHandler
{
    private const int HolyStoneMountSuccess = 800;
    private const int HolyStoneRemoveSuccess = 1200;
    private const int HolyStoneDrillSuccess = 1500;
    private static readonly TimeSpan PendingUnequipFollowupTtl = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan ForgeSelectionTtl = TimeSpan.FromMinutes(2);
    private static readonly TimeSpan PositionPersistInterval = TimeSpan.FromSeconds(2);
    private readonly ClientSession _session;
    private readonly IGameStore _store;
    private readonly IAccountDirectory _accountDirectory;
    private readonly IAccountPresenceWriter _accountPresence;
    private readonly GameSessionRegistry _registry;
    private readonly ICharacterSnapshotReader _characterSnapshots;
    private readonly ICharacterRuntimeProjectionReader
        _characterRuntimeProjections;
    private readonly IOwnedPetSnapshotReader _ownedPetSnapshots;
    private readonly ISealedPetSnapshotReader? _sealedPetSnapshots;
    private readonly IWorldBossAreaControlStore _worldBossAreaControl;
    private readonly IWorldBossRespawnReader _worldBossRespawns;
    private readonly IWorldContentReader _worldContent;
    private readonly GameplayRuntimeCatalogs _gameplayCatalogs;
    private readonly GameplayItemContent? _itemContent;
    private readonly IPetContentCatalog? _petContent;
    private readonly DeveloperCommandOptions _developerCommands;
    private readonly Guid _commandConnectionId = Guid.NewGuid();
    private Guid? _loginPetCallOutOperationId;
    private readonly LegacyAuthenticationAccess?
        _legacyAuthenticationAccess;
    private AccountIdentity? _account;
    private GameCharacter? _character;
    private HydratedCharacterLoadSnapshot? _characterLoadSnapshot;
    private bool _characterSnapshotLoaded;
    private bool _characterSnapshotBootstrapPending;
    private PendingUnequipFollowup? _pendingUnequipFollowup;
    private GearEnhancerSelectionContext? _gearEnhancerSelectionContext;
    private HolyStoneCombinationSelectionContext?
        _holyStoneCombinationSelectionContext;
    private int? _gearMentorOperationPageSubId;
    private ForgeSlotSelection? _forgeEquipment;
    private ForgeSlotSelection? _forgePrimaryMaterial;
    private readonly ForgeOddsReservationSet _forgeOddsMaterials = new();
    private int? _forgeAccountId;
    private int? _forgeCharacterId;
    private long _forgeSelectionStartedTimestamp;
    private bool _registered;
    private bool _accountSessionRegistered;
    private bool _worldPresenceAnnounced;
    private bool _clientReadyReceived;
    private bool _playerDetailSent;
    private bool _enterUiReadyReceived;
    private bool _postEnterBootstrapSent;
    private DateTime _lastPositionPersistUtc = DateTime.MinValue;
    private DateTimeOffset _nextBasicAttackAt = DateTimeOffset.MinValue;
    private readonly Dictionary<uint, DateTimeOffset> _nextSkillCastAt = [];
    private readonly SemaphoreSlim _characterStateGate = new(1, 1);
    private bool _positionDirty;
    private readonly Dictionary<uint, NpcSpawnDefinition> _mapNpcsByInteractionId = new();
    private WorldSectorVisibilityTracker<NpcSpawnDefinition>? _npcVisibility;

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        RegisterSkillCastInterruption();
        try
        {
            StartNpcCatalogUpdates();
            StartRealtimeMovement(cancellationToken);
            while (!cancellationToken.IsCancellationRequested)
            {
                var packet = await _session.ReadPacketAsync(cancellationToken);
                if (packet is null)
                {
                    return;
                }

                await _characterStateGate.WaitAsync(cancellationToken);
                try
                {
                    using var activity = ServerActivity.StartPacket(
                        ServerTraceOperation.GamePacket,
                        "game",
                        _session.IsSecure ? "tls" : "raw_tcp");
                    try
                    {
                        await HandlePacketAsync(packet, cancellationToken);
                        activity.Complete(
                            ServerTraceOutcome.Accepted);
                    }
                    catch (OperationCanceledException)
                    {
                        activity.Complete(
                            ServerTraceOutcome.Cancelled);
                        throw;
                    }
<<<<<<< HEAD
                    catch (Exception ex)
                    {
                        activity.Complete(
                            ServerTraceOutcome.Faulted);
                        // A fault here ends the session. Record it on stderr so
                        // the cause survives the structured console boundary,
                        // which folds legacy Console output into counters.
                        Console.Error.WriteLine(
                            $"[game-fault] opcode={packet.Opcode} " +
                            $"name={Opcodes.Name(packet.Opcode)} " +
                            $"len={packet.Length} " +
                            $"character={_character?.Name ?? "(none)"} " +
                            $"{ex.GetType().Name}: {ex.Message}");
=======
                    catch
                    {
                        activity.Complete(
                            ServerTraceOutcome.Faulted);
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
                        throw;
                    }
                }
                finally
                {
                    _characterStateGate.Release();
                }
            }
        }
        finally
        {
            await StopRealtimeMovementAsync();
            await StopNpcCatalogUpdatesAsync();
            await StopPetOwnerMergeEnergyLifecycleAsync();
            UnregisterSkillCastInterruption();
            await StopPendingSkillCastsAsync();

            ClearGearEnhancerSelection();
            ClearInstanceCallerPageContext();
            try
            {
                await _registry.FinishProgressionBoostOnlineSessionAsync(
                    _session,
                    DateTimeOffset.UtcNow,
                    CancellationToken.None);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[status] failed saving final online boost interval: {ex.Message}");
            }

            try
            {
                await _registry.FinishZodiacOnlineSessionAsync(
                    _session,
                    DateTimeOffset.UtcNow,
                    CancellationToken.None);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[zodiac] failed saving final online interval: {ex.Message}");
            }

            try
            {
                await EndPetOwnerMergeForSessionExitAsync();
            }
            catch (Exception ex)
            {
                Console.WriteLine(
                    $"[pet] failed ending owner Merge on session exit: {ex.Message}");
            }

            await DiscardPetGrowthPreviewForSessionExitAsync();

            if (_registered)
            {
                await LeavePartyForSessionExitAsync();
                try
                {
                    await BroadcastPlayerLeaveAsync(CancellationToken.None);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[world] failed broadcasting leave: {ex.Message}");
                }

                if (_character is { } character &&
                    TryGetCharacterOwnership(
                        character,
                        out var ownership))
                {
                    _registry.Remove(_session, ownership);
                }
                else
                {
                    _registry.Remove(_session);
                }

                _registered = false;
            }

            // Also clears a status state preserved across a revive if re-entry
            // failed before the session could rejoin the world registry.
            _registry.RemovePlayerStatusState(_session);

            await FinalizeCheckpointOwnershipAsync();

            if (_account is not null && _accountSessionRegistered)
            {
                var removedCurrentSession = _registry.RemoveAccountSession(_account.Id, _session);
                if (removedCurrentSession)
                {
                    await _accountPresence.MarkAccountOfflineAsync(
                        _account.Id,
                        CancellationToken.None);
                    Console.WriteLine($"[game] marked offline account={_account.Username}");
                }
            }

            _characterStateGate.Dispose();
        }
    }

}
