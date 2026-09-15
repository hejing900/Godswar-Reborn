using Godswar.Server.Domain.World.Content;

namespace Godswar.Server.Packets;

internal static partial class PacketBuilder
{
    // Exact opcode-10071 streams captured from the reference server on
    // 2026-08-28. CapitalNpcShopCatalog patches only the authoritative local
    // interaction ID and the character's current display balance.
    private const string PetMerchantCatalogGzip =
        "H4sIAAAAAAAEAO3ZvUtCURjH8XM1ISjDCKEao7CguSwIBLegqaCmsGho7i9wikb/hOZocGpqamqIpogyK3uzMu3FtBcIbnKPF4VjFHi+Q3CeQe65Xj/Pg1x/Xu5N+GZD00EhhLfNqryKQEgIu0FZlnDe/616PbY956mt3Q91anCTLarbD807AM0bhuYdg+aNaXBLdUe6mwsa3LRPdRc1uGtdqjulwd30q+6SBjfi9ypuNPiTa/3J7bFs+6tVnbegwY23q24RcsvQ9/AJzZuo5rHlDTi7jpo8P4KV8yOWU/ukIPcEcs8gNwO5V5B7DblZyL2F3HvIzUHuA+TmIbcAuY+Q+wS5dXnsrJ+hPkUNbjxcO9TdeoXcEuSWIfcNct+peQebd9dXVbdjiHG7IbcPcochdwRyI5A7CbkzkFvLY7lnHupj8liWyePqvCaPnTJ5LMvksSw3jz3V+xUXGn5/jfqkIfcccu8g9xhybyD3FHIvIfcFcj8gdxT6XxqH3CjkbkDuBORGILcuj511EuqzBbnbkLsDubuQuw+5B5CbgtwM5GYhNw+5y9D12wrk7kHuIeRm8Otj+dA+B/UpQa7JY1kmj2WZPJZl8ljWf8vjb8jZRBDwJgAA";

    private const string SkillVendorCatalogGzip =
        "H4sIAAAAAAAEAO3ZzUtUURzG8Tsvas3YKGZiaWUvYKSgoYta1CJoP2BgUGRQkKDgQC4qCNoEgkEXDAoSEmxRi0LatmsR0Wr+gBZF1CIXRQSBQTrOmUnp90wt5nsWwfktZC4On3O53PvMM2fihtHeWzuiKEq3Jkp/o1Ol16tiEomo/P9/TTZZeu+m4+rrPsB9LdzjgPty0zurLw94coc8uZ2AO7PVuv2AOyXck4BbFO5BwN2fte5RwM0LdxhwXzVb94QntwtwW1usOwC4S+3WPQa439qs203cD+J849953FA+7gXWiTvsOnsBd7DbuoOAe1i4hwD3xW7r9gDu9T3WDXnsJuSxm5DHbv7XPE5U+nFbR33rNNfoxxnAVf34XZ3XZd19K9xfgDsueuxHwFX9+Isn9zPgFpPW/QG4cZN1VwE3v8W6WeD+LYjPj+/E9RXue8BVefzVk5sErm9R5Pwn4HyP5Ky7DLgfhLuRx+7mzgHXRX1OpQB3vfv86a4A16XQad1G4HxVn28BXNXnfwLXQfXuJuB8l3usG/LYTchjNyGP3VTzOFnpx8+317fOthr9+AHgqn48B7iqFz715C4CruqbM4Cr9iseA67KzXnAVfsgdwE3J/YVngHuTZFDs4Crvv8/AtxpkRdPAHdBnO9D4rkQ+wq3AVftK9wjnguxr7uRx+ny8QKRmzvtOncAV/XN+4C7JPZ5Y8B9s8+6IY/dhDx2E/LYTchjN9U8TlX68Y32+tbJ1ejHFwFX9eOzgKt67BVP7lXAVXmcB9x5kW8TgDucsu4lwFV5fA5wVzLWnfTkTgOu+v4/Argq568Bbka4U8RzIfL4MuCq/dfTgBv95fe8VLqxfDwGrKNyvwC453dZdxRwVe8eB9wB4V4g7g/R588QuSn6fMhjNyGP3YQ8duMrj9cAbinK7YAsAAA=";

    private const string PropsVendorCatalogGzip =
        "H4sIAAAAAAAEAJvAGq4eKMrAwMDMyLigjZFBhoeB4T8WwMjIwMhABOBn+v/fHYlPlKZRMApGwSgYBQwTYOUxCzu4PF7Ij7M8ZiXGPEZgeSyJzIfSi6hgbgAWc/dRwVwuLObup4K5GljMPUAFc39hMRdPvCUTay6J8Ua0udjibRSMglGACWDlMSO0PDZSpqx9LAvMfwp+CD5MkzEVzAW5D91cE2q4dyE7hrk2VDBXQB3Bh2mypYK5AYcxzbWjgrkTLjBjmGtPBXM3FHJjmDsKRsEowASw8piJhQdcHrMIUJb/mID578FkFjgfpsmMCuZiK9/MqWAutnLeggrmYivnc3G3N4k294MnE4a5yTQyN54K5l5ABANcUwKNzPXTp9zc90gqYcwIGpmbRCNzSwQpNxdbvT8KaAtg5TEzCye4PF4jRlk8qgHjEVkhjL2SCuZiG1dYRSNze8wpN/c/orkJ11RjQRtztexpY+4KKoQvNnMb1GmTzlipEG/YzB0Fo4AeAADTMbkL0BsAAA==";

    private static readonly Lazy<byte[]> PetMerchantCatalog = new(
        () => InflateCatalog(
            PetMerchantCatalogGzip,
            expectedLength: 9_968,
            expectedPacketCount: 7,
            expectedCapturedNpcId: 5_459));

    private static readonly Lazy<byte[]> SkillVendorCatalog = new(
        () => InflateCatalog(
            SkillVendorCatalogGzip,
            expectedLength: 11_392,
            expectedPacketCount: 8,
            expectedCapturedNpcId: 5_509));

    private static readonly Lazy<byte[]> PropsVendorCatalog = new(
        () => FilterUnsupportedCatalogItems(
            InflateCatalog(
                PropsVendorCatalogGzip,
                expectedLength: 7_120,
                expectedPacketCount: 5,
                expectedCapturedNpcId: 5_457),
            [14_085]));

    private static byte[] GetCapturedCapitalShopCatalogSource(
        CapitalNpcServiceKind service) =>
        service switch
        {
            CapitalNpcServiceKind.PetMerchant => PetMerchantCatalog.Value,
            CapitalNpcServiceKind.SkillVendor => SkillVendorCatalog.Value,
            CapitalNpcServiceKind.PropsVendor => PropsVendorCatalog.Value,
            _ => throw new ArgumentOutOfRangeException(
                nameof(service),
                service,
                "The selected capital NPC is not a shop.")
        };
}
