namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// The Wishing Pool's second service, <c>NPC_FLAG_SYS_LOSTBOOK = 24</c>. The
    /// client names the entry "Make a wish with the Lost Book" and the reference
    /// server advertised it beside the skill-book wish, so the pool answers three
    /// wish kinds, one per advertised function number: 16 skill book, 24 lost book,
    /// 50 divine.
    /// </summary>
    private const int WishingPoolLostBookPage = 24;

    /// <summary>
    /// The Wishing Pool's third service, <c>NPC_FLAG_SYS_LUCKYGODS = 50</c>.
    /// </summary>
    private const int WishingPoolLuckyGodsPage = 50;

    /// <summary>
    /// The divine wish's own gate: <c>NF_L0_L012</c> reports that a wish needs
    /// level 55.
    /// </summary>
    private const int WishingPoolLuckyGodsMinimumLevel = 55;

    /// <summary>
    /// The lost-book page's opening answer, which is the reference server's own:
    /// <c>10070 {5212, 24, 101, 1, 2}</c>.
    /// </summary>
    /// <remarks>
    /// <c>101</c> is the header line of <c>NpcFunLostBook.lua</c> rather than a
    /// button - its branch watches <c>SubID % 2000 == 101</c> and prints the wishes
    /// left as <c>10 - (SubID - 101) / 2000</c>, so a plain <c>101</c> reads "you
    /// still have 10 wishes left". <c>1</c> and <c>2</c> are the page's two
    /// buttons, "*Use Incomplete Lost Book" and "*Use Lost Book".
    /// </remarks>
    private static readonly int[] WishingPoolLostBookMenu = [101, 1, 2];

    /// <summary>
    /// Both lost-book buttons lead to the wish itself, which this server does not
    /// run, so they are answered with the script's own missing-book line
    /// (<c>NF_L0_BK601</c>). It is a result, so the window closes on it.
    /// </summary>
    private static readonly int[] WishingPoolLostBookNoBook = [601];

    /// <summary>
    /// The divine wish's first page: the rules line and the two gods to choose
    /// between, whose buttons the script raises at <c>25,175</c> and
    /// <c>25,195</c>, plus the claim entry at <c>25,215</c>.
    /// </summary>
    private static readonly int[] WishingPoolLuckyMenu = [100, 101, 1000];

    /// <summary>
    /// The line the script reports below level 55 (<c>NF_L0_L012</c>).
    /// </summary>
    private static readonly int[] WishingPoolLuckyLevelReply = [1001];

    /// <summary>
    /// The claim entry's answer for a player holding no prize. The script only
    /// handles <c>201</c> off its first page, which is where the claim is clicked
    /// from, and it prints <c>NF_L0_L016</c>.
    /// </summary>
    private static readonly int[] WishingPoolLuckyNoPrize = [201];

    /// <summary>
    /// The answer to picking a god. The wish's luck belongs to an economy this
    /// server does not run, so the honest line is the script's own "the God you
    /// have just selected is not in the mood to grant wishes at the moment", which
    /// it computes as <c>8 + attempts * 10</c>. The number is the script's own
    /// daily allowance of ten attempts (<c>NF_L0_L001</c>).
    /// </summary>
    private static readonly int[] WishingPoolLuckyNoWish = [108];
}
