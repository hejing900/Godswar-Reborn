namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// What one number hands to the client's function window.
    /// </summary>
    /// <remarks>
    /// The window decides everything else: the label, the position and whether it
    /// closes. <see cref="ZeusDialogueKind.Result"/> is the one kind the script
    /// ends with <c>NPCFUN:EndMessage(true)</c>, so a reply that carries it must
    /// carry nothing else.
    /// </remarks>
    internal enum ZeusDialogueKind
    {
        /// <summary>A clickable entry.</summary>
        Button,

        /// <summary>A line of text that leaves the window open.</summary>
        Text,

        /// <summary>A line of text the script closes the window on.</summary>
        Result
    }

    /// <summary>
    /// One transcribed number of <c>NpcFunZeus.lua</c>. <see cref="LabelKey"/> is
    /// the client text key the script draws for it, recorded so the transcription
    /// can be checked against <c>LuaText.lua</c> without leaving this file.
    /// </summary>
    internal readonly record struct ZeusDialogueEntry(
        ZeusDialogueKind Kind,
        int SubId,
        string LabelKey);

    /// <summary>
    /// The follower's function number, <c>NPC_FLAG_SYS_ZEUS</c> in the client's
    /// own <c>NpcFun.lua</c>. It selects <c>NpcFunZeus_SetText</c>.
    /// </summary>
    private const int ZeusGiftFunctionNumber = 26;

    /// <summary>
    /// The follower's function list. It holds one entry because the follower's
    /// dialogue is a single script page sequence: the higher pages are reached by
    /// answering with their numbers, never by opening another entry.
    /// </summary>
    /// <remarks>
    /// An earlier revision advertised <c>[26, 6, 7]</c> to reach the script's later
    /// pages. Those two numbers are other people's functions -
    /// <c>NPC_FLAG_GUILDQUEST</c> and <c>NPC_FLAG_ACTIVITY</c> - so the guide's
    /// window offered "Guild Quest" and "Item Exchange" as if they were services of
    /// his, and neither of them drew a Zeus page.
    /// </remarks>
    private static readonly int[] ZeusGiftFunctionList = [ZeusGiftFunctionNumber];

    /// <summary>
    /// The level the follower turns away (<c>NF_L0_Z100</c>).
    /// </summary>
    internal const int ZeusGiftMinimumLevel = 55;

    /// <summary>
    /// The value the client sends when it wants the current page's entries rather
    /// than reporting a click.
    /// </summary>
    private const int ZeusGiftOpeningRequest = -1;

    /// <summary>
    /// The reply that turns away a character below the level (page 1, result).
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftLevelReply =
    [
        new(ZeusDialogueKind.Result, 100, "NF_L0_Z100")
    ];

    /// <summary>
    /// Page 1 of the follower's dialogue: his invitation and the three services he
    /// offers.
    /// </summary>
    /// <remarks>
    /// The script puts all three entries on rows of their own - <c>1200</c> at
    /// <c>25,135</c>, <c>1201</c> at <c>25,155</c> and <c>101</c> at <c>25,175</c> -
    /// so one reply may carry them together. The rows they leave free belong to the
    /// other Zeus endpoint: <c>1000</c>/<c>1001</c>/<c>1002</c>/<c>1003</c> are the
    /// gift-delivery entries drawn on the same page, and <c>100</c> is the level
    /// reply, which shares <c>1200</c>'s row because it never appears beside it.
    /// </remarks>
    private static readonly ZeusDialogueEntry[] ZeusGiftOpeningMenu =
    [
        new(ZeusDialogueKind.Text, 1511, "NF_L0_Z1511"),
        new(ZeusDialogueKind.Button, 1200, "NF_L0_Z1200"),
        new(ZeusDialogueKind.Button, 1201, "NF_L0_Z1201"),
        new(ZeusDialogueKind.Button, 101, "NF_L0_Z101")
    ];

    /// <summary>
    /// Page 2: the deposit form, which the script draws as a text line plus the
    /// stone input field (<c>NF_L0_Z1202</c>).
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftDepositForm =
    [
        new(ZeusDialogueKind.Text, 1202, "NF_L0_Z1202")
    ];

    /// <summary>
    /// Page 2: what the player may exchange for.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftExchangeMenu =
    [
        new(ZeusDialogueKind.Button, 1203, "NF_L0_Z1203"),
        new(ZeusDialogueKind.Button, 1204, "NF_L0_Z1204"),
        new(ZeusDialogueKind.Button, 1205, "NF_L0_Z1205")
    ];

    /// <summary>
    /// Page 2: the goods the luck of the exchange decides. The script lays the
    /// eight entries out in two columns - <c>200</c>-<c>204</c> down
    /// <c>25,155</c>-<c>25,235</c> and <c>205</c>-<c>207</c> down
    /// <c>320,155</c>-<c>320,195</c> - so the whole list fits in one reply.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftLuckMenu =
    [
        new(ZeusDialogueKind.Text, 1517, "NF_L0_Z1517"),
        new(ZeusDialogueKind.Button, 200, "NF_Z_B200"),
        new(ZeusDialogueKind.Button, 201, "NF_Z_B201"),
        new(ZeusDialogueKind.Button, 202, "NF_Z_B202"),
        new(ZeusDialogueKind.Button, 203, "NF_Z_B203"),
        new(ZeusDialogueKind.Button, 204, "NF_Z_B204"),
        new(ZeusDialogueKind.Button, 205, "NF_Z_B205"),
        new(ZeusDialogueKind.Button, 206, "NF_Z_B206"),
        new(ZeusDialogueKind.Button, 207, "NF_Z_B207")
    ];

    /// <summary>
    /// Page 3: the deposit went through.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftDepositResult =
    [
        new(ZeusDialogueKind.Result, 1206, "NF_L0_Z1206")
    ];

    /// <summary>
    /// Page 3: the ordinary goods, with the warning the script prints above them.
    /// The five entries sit at <c>25,135</c>-<c>25,215</c>.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftOrdinaryMenu =
    [
        new(ZeusDialogueKind.Text, 1518, "NF_L0_Z1518"),
        new(ZeusDialogueKind.Button, 1207, "NF_L0_Z1207"),
        new(ZeusDialogueKind.Button, 1208, "NF_L0_Z1208"),
        new(ZeusDialogueKind.Button, 1209, "NF_L0_Z1209"),
        new(ZeusDialogueKind.Button, 1210, "NF_L0_Z1210"),
        new(ZeusDialogueKind.Button, 1211, "NF_L0_Z1211")
    ];

    /// <summary>
    /// Page 3: the limited goods, with the script's warning about them.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftLimitedMenu =
    [
        new(ZeusDialogueKind.Text, 1516, "NF_L0_Z1516"),
        new(ZeusDialogueKind.Button, 4000, "NF_L0_Z1230"),
        new(ZeusDialogueKind.Button, 4001, "NF_L0_Z1234"),
        new(ZeusDialogueKind.Button, 4002, "NF_L0_Z1235"),
        new(ZeusDialogueKind.Button, 4003, "NF_L0_Z1232"),
        new(ZeusDialogueKind.Button, 4004, "NF_L0_Z1233"),
        new(ZeusDialogueKind.Button, 4005, "NF_L0_Z1236"),
        new(ZeusDialogueKind.Button, 4006, "NF_L0_Z1231")
    ];

    /// <summary>
    /// Page 3: the experience and talent points were redeemed.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftRedeemResult =
    [
        new(ZeusDialogueKind.Result, 1611, "NF_L0_Z1113")
    ];

    /// <summary>
    /// Page 3: the dust bracket, which is what the luck of an exchange is settled
    /// with. <c>3000</c> shows the bracket itself and clears the text line, so it
    /// goes before <c>3001</c>, whose instruction is the line that must stay up.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftDustBracket =
    [
        new(ZeusDialogueKind.Text, 3000, "NF_L0_Z1212"),
        new(ZeusDialogueKind.Text, 3001, "NF_L0_Z1213")
    ];

    /// <summary>
    /// Page 3: the same bracket with the claim the script puts beside it
    /// (<c>NF_Z_B302</c>, "I've won the prize!").
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftLuckBracket =
    [
        new(ZeusDialogueKind.Text, 3000, "NF_L0_Z1212"),
        new(ZeusDialogueKind.Text, 3001, "NF_L0_Z1213"),
        new(ZeusDialogueKind.Button, 302, "NF_Z_B302")
    ];

    /// <summary>
    /// Page 4: the limited goods have run out by the time the exchange is settled.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftOutOfStock =
    [
        new(ZeusDialogueKind.Result, 5102, "NF_L0_Z1329")
    ];

    /// <summary>
    /// Page 4: the prizes the claim is settled against.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftPrizeMenu =
    [
        new(ZeusDialogueKind.Button, 1230, "NF_L0_Z1230"),
        new(ZeusDialogueKind.Button, 1231, "NF_L0_Z1231"),
        new(ZeusDialogueKind.Button, 1232, "NF_L0_Z1232"),
        new(ZeusDialogueKind.Button, 1233, "NF_L0_Z1233"),
        new(ZeusDialogueKind.Button, 1234, "NF_L0_Z1234"),
        new(ZeusDialogueKind.Button, 1235, "NF_L0_Z1235"),
        new(ZeusDialogueKind.Button, 1236, "NF_L0_Z1236")
    ];

    /// <summary>
    /// Page 5: the prize was handed over.
    /// </summary>
    private static readonly ZeusDialogueEntry[] ZeusGiftPrizeClaimed =
    [
        new(ZeusDialogueKind.Result, 3007, "NF_L0_Z1222")
    ];

    /// <summary>
    /// What each number the client can send is answered with.
    /// </summary>
    /// <remarks>
    /// A reply cannot name a page: the function number comes back untouched, and a
    /// number only draws on the page whose branch it sits in. How the client picks
    /// that page is settled by the instance caller, which this server already
    /// answers at two levels - it sends dialog index <c>9</c> with both
    /// <c>[11,14,15]</c> and <c>[206,204,205,207]</c> and the client draws page one
    /// for the first and page two for the second. The page therefore follows the
    /// sequence of replies inside one dialogue, and every value below holds the
    /// numbers of the step its key leads to.
    ///
    /// The ordinary goods are answered with the dust bracket because that is the
    /// script's own order - the bracket is page 4, the shelf that sells them is
    /// page 3 - and the same holds for the follow-ups of the limited and lucky
    /// shelves. Nothing here reports a reward: the follower's economy is not
    /// implemented, so every branch stops at the line the client draws.
    /// </remarks>
    private static readonly Dictionary<int, ZeusDialogueEntry[]> ZeusGiftSteps = new()
    {
        [1200] = ZeusGiftDepositForm,
        [1201] = ZeusGiftExchangeMenu,
        [101] = ZeusGiftLuckMenu,

        [1202] = ZeusGiftDepositResult,
        [1203] = ZeusGiftOrdinaryMenu,
        [1204] = ZeusGiftLimitedMenu,
        [1205] = ZeusGiftRedeemResult,

        [200] = ZeusGiftLuckBracket,
        [201] = ZeusGiftLuckBracket,
        [202] = ZeusGiftLuckBracket,
        [203] = ZeusGiftLuckBracket,
        [204] = ZeusGiftLuckBracket,
        [205] = ZeusGiftLuckBracket,
        [206] = ZeusGiftLuckBracket,
        [207] = ZeusGiftLuckBracket,

        [1207] = ZeusGiftDustBracket,
        [1208] = ZeusGiftDustBracket,
        [1209] = ZeusGiftDustBracket,
        [1210] = ZeusGiftDustBracket,
        [1211] = ZeusGiftDustBracket,

        [4000] = ZeusGiftOutOfStock,
        [4001] = ZeusGiftOutOfStock,
        [4002] = ZeusGiftOutOfStock,
        [4003] = ZeusGiftOutOfStock,
        [4004] = ZeusGiftOutOfStock,
        [4005] = ZeusGiftOutOfStock,
        [4006] = ZeusGiftOutOfStock,

        [302] = ZeusGiftPrizeMenu,

        [1230] = ZeusGiftPrizeClaimed,
        [1231] = ZeusGiftPrizeClaimed,
        [1232] = ZeusGiftPrizeClaimed,
        [1233] = ZeusGiftPrizeClaimed,
        [1234] = ZeusGiftPrizeClaimed,
        [1235] = ZeusGiftPrizeClaimed,
        [1236] = ZeusGiftPrizeClaimed
    };
}
