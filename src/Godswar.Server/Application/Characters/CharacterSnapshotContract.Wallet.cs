namespace Godswar.Server.Application.Characters;

internal static partial class CharacterSnapshotContract
{
    private static void ValidateWallet(CharacterWalletSnapshot wallet)
    {
        if (wallet is null)
        {
            throw Invalid("Character wallet is missing.");
        }

        if (wallet.Silver < 0 ||
            wallet.Gold < 0 ||
            wallet.BindingGold < 0 ||
            wallet.MedusaHonorPoints < 0 ||
<<<<<<< HEAD
            wallet.MedusaRewardRevision < 0 ||
            wallet.ExchangePoint < 0 ||
            wallet.ExchangeMedal < 0)
=======
            wallet.MedusaRewardRevision < 0)
>>>>>>> da67a14d626fe493b373a8c188aeb4ec075ac3b0
        {
            throw Invalid("Character wallet contains a negative balance.");
        }
    }
}
