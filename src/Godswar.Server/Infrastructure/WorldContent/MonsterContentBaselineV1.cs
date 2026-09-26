using System.Reflection;
using System.Security.Cryptography;
using Godswar.Server.Application.World;
using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Infrastructure.WorldContent;

internal static class MonsterContentBaselineV1
{
    public const int ExpectedEntryCount = 3191;
    public const string ExpectedRevision =
        "968B5D9EF97C62279EB1E84F7E6CD45AEC403EFD14CBF106652BEB8BB538A305";
    public const string ExpectedArtifactSha256 =
        "FB5AB48845583322CAC5911ACFA5B6466772718A8D6AEBC09BD8809ABA50F98D";
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
