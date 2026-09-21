namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// Which dialogue set an NPC of the Zeus gift event answers with.
    /// </summary>
    /// <remarks>
    /// The two endpoints share one client script, <c>NpcFunZeus.lua</c>, and the
    /// script's first page carries both of their entry groups. The groups occupy
    /// the same rows - the believer's <c>1200</c>/<c>1201</c>/<c>101</c> at
    /// <c>25,135</c>/<c>155</c>/<c>175</c> and the saint's
    /// <c>1000</c>/<c>1001</c>/<c>1002</c>/<c>1003</c> at
    /// <c>25,135</c>/<c>155</c>/<c>175</c>/<c>195</c> - so which set an endpoint
    /// answers with is what keeps the two windows apart.
    /// </remarks>
    internal readonly record struct ZeusGiftDialogueSet(
        IReadOnlyList<ZeusDialogueEntry> OpeningMenu,
        IReadOnlyDictionary<int, ZeusDialogueEntry[]> Steps);

    /// <summary>
    /// The believing guide's set, which is the one the shipped dialogue answers
    /// with: his invitation followed by the deposit, the exchange and the luck of
    /// the event.
    /// </summary>
    internal static ZeusGiftDialogueSet ZeusGiftBelieverDialogue =>
        new(ZeusGiftOpeningMenu, ZeusGiftSteps);

    /// <summary>
    /// The praying saint's set: he is the endpoint a gift is handed to, so his
    /// first page offers the delivery entries and his second the basket.
    /// </summary>
    internal static ZeusGiftDialogueSet ZeusGiftSaintDialogue =>
        new(ZeusGiftSaintOpeningMenu, ZeusGiftSaintSteps);

    /// <summary>
    /// The saint's first page: the same invitation and the four delivery entries,
    /// transcribed from page 1 of <c>NpcFunZeus.lua</c>.
    /// </summary>
    /// <remarks>
    /// The four entries sit on rows of their own - <c>1000</c> at <c>25,135</c>,
    /// <c>1001</c> at <c>25,155</c>, <c>1002</c> at <c>25,175</c> and
    /// <c>1003</c> at <c>25,195</c> - so the whole group fits in one reply. The
    /// seven equipment grades (<c>Z1401</c>-<c>Z1407</c>) and the dust names are
    /// drawn by the same page as lines of text, but each reply can only leave one
    /// line standing, so they are not sent: the script gives no way to reach them
    /// one after another inside a single dialogue.
    /// </remarks>
    private static readonly ZeusDialogueEntry[] ZeusGiftSaintOpeningMenu =
    [
        new(ZeusDialogueKind.Text, 1511, "NF_L0_Z1511"),
        new(ZeusDialogueKind.Button, 1000, "NF_L0_Z1000"),
        new(ZeusDialogueKind.Button, 1001, "NF_L0_Z1001"),
        new(ZeusDialogueKind.Button, 1002, "NF_L0_Z1002"),
        new(ZeusDialogueKind.Button, 1003, "NF_L0_Z1003")
    ];

    /// <summary>
    /// Second page: the basket. <c>1005</c> shows the slot the gift is placed in
    /// and prints the instruction, <c>1006</c> hands the gift over and
    /// <c>1008</c> walks away. The script's other two answers to the same question
    /// - <c>1007</c> "Go ahead. I can't get it myself." and <c>1009</c> "Let me
    /// think about it." - are drawn on <c>1006</c>'s and the empty row's own
    /// coordinates, so they cannot travel with the pair that is sent here.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftSaintBasket =
    [
        new(ZeusDialogueKind.Text, 1005, "NF_L0_Z1005"),
        new(ZeusDialogueKind.Button, 1006, "NF_L0_Z1006"),
        new(ZeusDialogueKind.Button, 1008, "NF_L0_Z1008")
    ];

    /// <summary>
    /// Third page: the gift was accepted.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftSaintAccepted =
    [
        new(ZeusDialogueKind.Result, 1011, "NF_L0_Z1011")
    ];

    /// <summary>
    /// Third page: the player left without handing anything over.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftSaintNothingPlaced =
    [
        new(ZeusDialogueKind.Result, 1503, "NF_L0_Z1503")
    ];

    /// <summary>
    /// Third page: the "try another way" answer, which the script closes with the
    /// same line it uses for a selection it did not receive.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftSaintTryAnotherWay =
    [
        new(ZeusDialogueKind.Result, 1102, "NF_L0_Z1115")
    ];

    /// <summary>
    /// What each number the saint's window can send is answered with.
    /// </summary>
    private static readonly Dictionary<int, ZeusDialogueEntry[]>
        ZeusGiftSaintSteps = new()
        {
            [1000] = ZeusGiftSaintBasket,
            [1001] = ZeusGiftSaintBasket,
            [1002] = ZeusGiftSaintBasket,
            [1003] = ZeusGiftSaintTryAnotherWay,
            [1006] = ZeusGiftSaintAccepted,
            [1008] = ZeusGiftSaintNothingPlaced
        };
}
