using Godswar.Server.Packets;
using Godswar.Server.Protocol;

namespace Godswar.Server.Game;

internal sealed partial class GameClientHandler
{
    /// <summary>
    /// An NPC whose whole window is owned by one client script: the server opens
    /// the function, and every step afterwards is a list of numbers the script
    /// draws.
    /// </summary>
    /// <param name="FunctionNumber">
    /// The <c>NPC_FLAG_SYS_*</c> value that selects the client script. It is
    /// advertised in the open packet's function list and echoed back untouched in
    /// every reply.
    /// </param>
    /// <param name="OpeningMenu">
    /// The numbers of the first page, answered when the client asks for the
    /// current page's entries (<c>subId == -1</c>).
    /// </param>
    /// <param name="Steps">
    /// What each number the client can send is answered with. Every value holds
    /// numbers of the page the click leads to, because a number only draws on the
    /// page whose branch it sits in. The table covers every button the dialogue
    /// draws, so a number outside it is not a button of this dialogue's and is left
    /// unanswered.
    /// </param>
    internal readonly record struct ScriptedNpcDialogue(
        int FunctionNumber,
        IReadOnlyList<int> OpeningMenu,
        IReadOnlyDictionary<int, int[]> Steps);

    /// <summary>
    /// The Mysterious Elder, who hands out Sheepskin Scrolls and pieces the Lost
    /// Book together.
    /// </summary>
    /// <remarks>
    /// Transcribed from page 1 of <c>NpcFunOldMan.lua</c> (function
    /// <c>NPC_FLAG_SYS_OLDMAN = 23</c>, which the client labels "Story of the Lost
    /// Book"). The intro is the page's only text branch and the four entries sit at
    /// <c>25,165</c>, <c>25,185</c>, <c>25,205</c> and <c>25,225</c>, so the whole
    /// menu fits in one reply. The script's own <c>2</c> entry is commented out in
    /// the client, so it is not sent.
    /// </remarks>
    private static readonly ScriptedNpcDialogue MysteriousElderDialogue = new(
        FunctionNumber: 23,
        OpeningMenu: [1000, 1, 3, 4, 5],
        Steps: new Dictionary<int, int[]>
        {
            // "*Get a Sheepskin Scroll for free." The scroll itself is not
            // granted, so the answer is the script's daily-limit line rather than
            // its success line.
            [1] = [505],

            // The three combining entries - chapters 1+2+3, chapters 4+5+6 and all
            // seven. Each is answered with the script's own "not enough of the
            // item to be exchanged", which is what a bag without the chapters
            // gets.
            [3] = [601],
            [4] = [601],
            [5] = [601]
        });

    /// <summary>
    /// The Profession Mentor, who teaches and unlearns the four professions.
    /// </summary>
    /// <remarks>
    /// Transcribed from <c>NpcFunLifeSkill.lua</c> (function
    /// <c>NPC_FLAG_SYS_LIFESKILL = 64</c>). The client's own configuration names
    /// this NPC "Profession Mentor" in <c>NpcName.dat</c> and 专业导师 in
    /// <c>Settings/Sys/NPC.INI</c>.
    ///
    /// Page 1 is the four entries at <c>25,155</c>-<c>25,215</c>. Page 2 answers
    /// the learn entry with the profession overview and the four professions, the
    /// unlearn entry with its warning and its confirmation, and the other two with
    /// the script's information lines. Page 3 answers each profession with its own
    /// description and a learn button at <c>25,135</c>. The learn buttons are
    /// answered from page 4 with the script's missing-skillbook line, because no
    /// profession skillbook is granted or consumed here.
    /// </remarks>
    private static readonly ScriptedNpcDialogue ProfessionMentorDialogue = new(
        FunctionNumber: 64,
        OpeningMenu: [101, 102, 103, 104],
        Steps: new Dictionary<int, int[]>
        {
            // "*Learn Profession" - the overview text and the four professions.
            [101] = [201, 202, 203, 204, 205],

            // "*Unlearn Profession" - the warning and its confirmation.
            [102] = [206, 207],

            // "*Props Creation" - what each profession makes. The client also
            // raises its crafting window for this entry through its message
            // callback, which this server has no packet for.
            [103] = [208],

            // "*Professions Info" - the overview on its own, which the window's
            // own close button dismisses.
            [104] = [201],

            // The four professions, each with its description and a learn button.
            [202] = [301, 302],
            [203] = [303, 304],
            [204] = [305, 306],
            [205] = [307, 308],

            // The learn buttons. No skillbook is granted, so the script's own
            // missing-skillbook line is the answer.
            [302] = [402],
            [304] = [402],
            [306] = [402],
            [308] = [402],

            // The unlearn confirmation. Nothing is tracked as learned here, so the
            // script's own "you haven't learned anything" line is the answer.
            [207] = [309]
        });

    /// <summary>
    /// The Personal Helper, who enables batch use of consumables.
    /// </summary>
    /// <remarks>
    /// Transcribed from <c>NpcFunBatch.lua</c> (function
    /// <c>NPC_FLAG_SYS_BATCH = 107</c>, which the client labels "BATCH"). The
    /// script's first page is one branch that prints the instruction and shows the
    /// item slot and the quantity field. The batch itself is not run here, so the
    /// page has no second step and every later answer is the opening menu again.
    /// </remarks>
    private static readonly ScriptedNpcDialogue PersonalHelperDialogue = new(
        FunctionNumber: 107,
        OpeningMenu: [100],
        Steps: new Dictionary<int, int[]>());

    /// <summary>
    /// The Event Transporters, who send players to Sicily and to the Trojan
    /// Expedition.
    /// </summary>
    /// <remarks>
    /// Transcribed from page 1 of <c>NpcFunTranmit.lua</c> (function
    /// <c>NPC_FLAG_SYS_TRANMIT = 1</c>). Both entries are named by the shipped
    /// content rather than inferred: <c>700</c> is <c>NF_L0_700</c> "*Teleport to
    /// Sicily", which quests 1292-1306 send players to, and <c>900</c> is
    /// <c>NF_L0_TR800</c> "*To the Trojan Expedition", which the weekday
    /// announcement sends players to. The transports themselves are not wired, so
    /// each entry is answered with the script's own line about the event: the
    /// missing-spell refusal for Sicily and the opening hours for Troy.
    /// </remarks>
    private static readonly ScriptedNpcDialogue EventTransporterDialogue = new(
        FunctionNumber: 1,
        OpeningMenu: [700, 900],
        Steps: new Dictionary<int, int[]>
        {
            [700] = [2702],
            [701] = [2702],
            [900] = [2801]
        });

    /// <summary>
    /// The guild quest supervisor of both capitals.
    /// </summary>
    /// <remarks>
    /// Transcribed from page 1 of <c>NpcFunGuildQuest.lua</c> (function
    /// <c>NPC_FLAG_GUILDQUEST = 6</c>, which the client labels "Guild Quests").
    /// Page 1 prints <c>NF_L0_97</c> ("Please choose a quest for all guild
    /// members:") for every number and raises its two entries at <c>25,135</c> and
    /// <c>25,160</c>, so one reply carries both. The script's own <c>3</c> and
    /// <c>4</c> are aliases of those two buttons and <c>5</c>/<c>7</c> ("War
    /// Material Transportation") is drawn with <c>Visible(false)</c>, so none of
    /// them are sent. Issuing a guild quest is not run here, so both entries are
    /// answered with the script's own line for a player who may not issue one.
    /// </remarks>
    private static readonly ScriptedNpcDialogue GuildQuestSupervisorDialogue = new(
        FunctionNumber: 6,
        OpeningMenu: [1, 2],
        Steps: new Dictionary<int, int[]>
        {
            [1] = [1001],
            [2] = [1001]
        });

    /// <summary>
    /// The guild altar supervisor of both capitals, who builds and upgrades the
    /// guild's buildings and takes donations.
    /// </summary>
    /// <remarks>
    /// Transcribed from <c>NpcFunAltar.lua</c> (function
    /// <c>NPC_FLAG_SYS_ALTAR = 5</c>, which the client labels "Altar").
    ///
    /// The script reuses the same numbers on different pages - page one's
    /// <c>1</c>/<c>2</c>/<c>4</c> are the building types, page two's <c>1</c> is
    /// the Guild Footstone and page three's <c>1</c> is "Build New Building" - and a
    /// table keyed by the clicked number alone can hold only one meaning for each.
    /// Every reply below therefore offers only numbers that no earlier step of this
    /// dialogue uses, so the click that comes back can only mean one thing:
    ///
    ///   page 1  1/2/4      the three building types, at 25,135/155/175
    ///   page 2  5/6/3      basic buildings: Senior House at 25,135, Luxurious
    ///                      House at 25,155, then Super Guild Warehouse, whose
    ///                      branch sets no position at all and therefore takes the
    ///                      third button slot, which the window's own ladder places
    ///                      at 25,175 - the same spot the opening reply's
    ///                      <c>4</c> uses. The warehouse must come last: sent
    ///                      first it would sit on 25,135 and the Senior House
    ///                      would be drawn on top of it. The script gives 1/2/4
    ///                      away to page one, and 2 (the Common Guild Warehouse)
    ///                      has no position of its own either.
    ///   page 2  10-19      the ten god altars, 25,95-195 and 320,95-155
    ///   page 2  20-30      Advanced Altar 1-10 and the God Altar. The script sets
    ///                      no position for any of them, so they take the window's
    ///                      own slots in order - 25,135 to 25,235 and then 320,135
    ///                      to 320,215 - which is where the ladder in the client's
    ///                      NpcFun.lua puts slots one to eleven anyway.
    ///   page 3  200+N      the chosen building's own description: the script reads
    ///                      <c>SubID &gt;= 400</c> for ranks and keeps
    ///                      <c>201</c>-<c>206</c> for the basic buildings,
    ///                      <c>210</c>-<c>220</c> for the altars and
    ///                      <c>221</c>-<c>230</c> for the advanced ones, which is
    ///                      exactly page two's number plus 200.
    ///
    /// The description branches carry no <c>EndMessage</c>, so the window stays open
    /// on them. The guild's building economy is not run here, so the page-three
    /// action buttons (<c>1</c>/<c>2</c> share a position, <c>4</c>/<c>10</c> share
    /// another) and the page-four donation amounts are not sent: their outcomes are
    /// the script's <c>1000</c>-<c>1017</c> lines, which only draw from page five
    /// on and would need the guild gold, silver and contribution accounts to say
    /// anything true.
    /// </remarks>
    private static ScriptedNpcDialogue BuildGuildAltarDialogue()
    {
        var steps = new Dictionary<int, int[]>
        {
            [1] = [5, 6, 3],
            [2] = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            [4] = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30],
            [3] = [203],
            [5] = [205],
            [6] = [206]
        };
        for (var altar = 10; altar <= 30; altar++)
        {
            steps[altar] = [200 + altar];
        }

        return new ScriptedNpcDialogue(
            FunctionNumber: 5,
            OpeningMenu: [1, 2, 4],
            Steps: steps);
    }

    private static readonly ScriptedNpcDialogue GuildAltarDialogue =
        BuildGuildAltarDialogue();

    /// <summary>
    /// The guild member advisor of both capitals, who hands out the guild's
    /// double-experience and double-talent-point periods.
    /// </summary>
    /// <remarks>
    /// Transcribed from <c>NpcFunUionTime.lua</c> (function
    /// <c>NPC_FLAG_SYS_UNIONTIME = 8</c>, which the client's own table comments
    /// "guild welfare"). The NPC's description - "entitled to all the benefits of
    /// membership ... weekly prayer to double your EXP and talent points" - is
    /// answered only by this script's text (<c>NF_L0_UNION1</c> "*Double EXP
    /// Period", <c>NF_L0_UNION2</c> "*Double Talent Point Period",
    /// <c>NF_L0_UNION11</c>-<c>UNION30</c> the hourly claims).
    ///
    /// Page one's five buttons sit at 25,135/155/175/195/215, so one reply carries
    /// all of them. The claim entries open page two's hourly lists, and the inquiry
    /// is answered with the script's own level line, which it computes as
    /// <c>31 + (level + 1) * 500</c> - <c>531</c> reads the guild's double
    /// experience level as zero, which is what a server without guild levels can
    /// honestly report. Every claim ends on the script's own "insufficient time
    /// left to claim" line, and both period entries end on its "insufficient funds
    /// to upgrade the guild" line, because the guild gold, silver and level
    /// accounts those two would spend are not run here.
    /// </remarks>
    private static ScriptedNpcDialogue BuildGuildMemberAdvisorDialogue()
    {
        var steps = new Dictionary<int, int[]>
        {
            [1] = [300],
            [2] = [300],
            [3] = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            [4] = [21, 22, 23, 24, 25, 26, 27, 28, 29, 30],
            [5] = [531]
        };
        for (var hour = 11; hour <= 30; hour++)
        {
            steps[hour] = [352];
        }

        return new ScriptedNpcDialogue(
            FunctionNumber: 8,
            OpeningMenu: [1, 2, 3, 4, 5],
            Steps: steps);
    }

    private static readonly ScriptedNpcDialogue GuildMemberAdvisorDialogue =
        BuildGuildMemberAdvisorDialogue();

    /// <summary>
    /// The scripted dialogue an NPC answers with, or <see langword="null"/> when
    /// the NPC is not one of them.
    /// </summary>
    private static ScriptedNpcDialogue? ResolveScriptedNpcDialogue(
        NpcSpawnDefinition npc) => npc.NpcKey switch
        {
            "Athens_083" or "Sparta_083" => MysteriousElderDialogue,
            "Athens_120" or "Sparta_120" => ProfessionMentorDialogue,
            "Athens_139" or "Sparta_139" => PersonalHelperDialogue,
            "Athens_072" or "Sparta_072" => EventTransporterDialogue,
            "Athens_038" or "Sparta_039" => GuildQuestSupervisorDialogue,
            "Athens_050" or "Sparta_050" => GuildAltarDialogue,
            "Athens_051" or "Sparta_051" => GuildMemberAdvisorDialogue,
            _ => null
        };

    /// <summary>
    /// Opens a scripted NPC's function menu.
    /// </summary>
    private async Task SendScriptedNpcDialogueMenuAsync(
        NpcSpawnDefinition npc,
        ScriptedNpcDialogue dialogue,
        CancellationToken cancellationToken)
    {
        await _session.SendAsync(
            PacketBuilder.NpcDialogOpenAck(
                npc.InteractionId,
                [dialogue.FunctionNumber],
                npc.NpcKey),
            cancellationToken,
            "ScriptedNpcDialogueMenu");
        Console.WriteLine(
            $"[npc] scripted dialogue open npc={npc.InteractionId} " +
            $"key={npc.NpcKey} function={dialogue.FunctionNumber} " +
            $"menu=[{string.Join(',', dialogue.OpeningMenu)}]");
    }

    /// <summary>
    /// Answers one step of a scripted NPC's dialogue by the number the client
    /// sent, and logs every word of the request so a selector that lands in an
    /// unexpected word can be seen in the server log.
    /// </summary>
    private async Task HandleScriptedNpcDialogueAsync(
        NpcSpawnDefinition npc,
        ScriptedNpcDialogue dialogue,
        GamePacket packet,
        int dialogIndex,
        int subId,
        CancellationToken cancellationToken)
    {
        var payload = packet.Payload;
        var words = new List<string>();
        for (var index = 0; index < payload.Length / 4 && index < 7; index++)
        {
            words.Add(
                $"p{index * 4}=" +
                System.Buffers.Binary.BinaryPrimitives
                    .ReadInt32LittleEndian(payload.Slice(index * 4, 4)));
        }

        Console.WriteLine(
            $"[npc] scripted dialogue words npc={npc.InteractionId} " +
            $"key={npc.NpcKey} generic={subId} dialog={dialogIndex} " +
            $"len={packet.Length} {string.Join(' ', words)}");
        var selection = payload.Length >= 20
            ? System.Buffers.Binary.BinaryPrimitives
                .ReadInt32LittleEndian(payload.Slice(16, 4))
            : subId;
        if (selection < 0)
        {
            selection = subId;
        }

        if (selection < 0)
        {
            // The client is asking for the current page's entries.
            await SendScriptedNpcDialogueReplyAsync(
                npc,
                dialogue,
                dialogIndex,
                selection,
                dialogue.OpeningMenu,
                cancellationToken);
            return;
        }

        if (!dialogue.Steps.TryGetValue(selection, out var opened))
        {
            // Every button this dialogue draws is registered, so a number outside
            // the table cannot come from a button of its own. Nothing is sent: the
            // window keeps whatever it is showing.
            Console.WriteLine(
                $"[npc] scripted dialogue unregistered npc={npc.InteractionId} " +
                $"key={npc.NpcKey} selection={selection}");
            return;
        }

        await SendScriptedNpcDialogueReplyAsync(
            npc,
            dialogue,
            dialogIndex,
            selection,
            opened,
            cancellationToken);
    }

    private async Task SendScriptedNpcDialogueReplyAsync(
        NpcSpawnDefinition npc,
        ScriptedNpcDialogue dialogue,
        int dialogIndex,
        int selection,
        IReadOnlyList<int> reply,
        CancellationToken cancellationToken)
    {
        await _session.SendAsync(
            PacketBuilder.NpcFunctionActionResponse(
                npc.InteractionId,
                dialogIndex,
                [.. reply]),
            cancellationToken,
            "ScriptedNpcDialogueReply");
        Console.WriteLine(
            $"[npc] scripted dialogue reply npc={npc.InteractionId} " +
            $"key={npc.NpcKey} function={dialogue.FunctionNumber} " +
            $"selection={selection} sent=[{string.Join(',', reply)}]");
    }
}
