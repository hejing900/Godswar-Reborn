using System.Reflection;
using System.Security.Cryptography;
using Godswar.Server.Application.World;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Infrastructure.WorldContent;

internal static class MonsterContentBaselineV1
{
    public const int ExpectedEntryCount = 2921;
    public const string ExpectedRevision =
        "0DA1196AB603F5BE7C0703FA6A15CFCF3A5304257EBC9574E5B4DCE386C87754";
    public const string ExpectedArtifactSha256 =
        "25867D2A2C419BCFEF64AF241F5431141EE7A8CEF7AC2751E5723D6D4E34D9C3";
    public const string Source = "reviewed-capture-promotion-v1";

    private const string ResourceName =
        "Godswar.Server.Infrastructure.WorldContent." +
        "Baselines.MonsterContentBaseline.v1.gz";

    public static CapturedMonsterSpawn[] LoadDefinitions()
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var stream =
            assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidDataException(
                "The reviewed monster baseline resource is missing.");
        using var compressed = new MemoryStream();
        stream.CopyTo(compressed);
        var bytes = compressed.ToArray();
        var artifactHash = Convert.ToHexString(SHA256.HashData(bytes));
        if (!string.Equals(
                ExpectedArtifactSha256,
                artifactHash,
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "The reviewed monster baseline artifact checksum is invalid.");
        }

        var definitions = MonsterContentBaselineCodec.Deserialize(bytes);
        if (definitions.Length != ExpectedEntryCount)
        {
            throw new InvalidDataException(
                "The reviewed monster baseline entry count is invalid.");
        }

        var revision = WorldContentRevisionHasher.HashMonsters(definitions);
        if (!string.Equals(
                ExpectedRevision,
                revision.Sha256,
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "The reviewed monster baseline content revision is invalid.");
        }

        return definitions;
    }
}
