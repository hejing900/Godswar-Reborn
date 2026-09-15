"""Generate the full starter quest chain for both camps.

Scope: every quest in Quest.xml that an npc hands out, split into the two camps
the client ships in parallel. The client pairs its progressions by quest id - the
Sparta tutorial 518 mirrors the Athens 1518, the Sparta region quests handed out
by the Peloponnese npcs mirror the Athens ones handed out by the Marathon npcs -
so the camp of a quest is read from its own data rather than guessed:

  * a giver or responder carrying an Athens-side region key is Athens;
  * a giver or responder carrying a Sparta-side region key is Sparta;
  * a quest whose npcs are in neither (Thebes, Thermopylae, Parnassus, Mycenae,
    Troy, WarField - regions both camps visit) follows its id: 1000 and below is
    the Sparta copy, above it the Athens copy, which is the mirror pairing the
    client itself uses.

Each camp keeps its own order - its tutorials first, then by level - and its own
next-quest pointer, so a Sparta character is never sent to an Athens npc.

Rewards come from the quest text: the Append block lists Exp / TP / Silver / Gold
(EndText repeats it). Item rewards are not in the text at all, so none are emitted.

The C# shape stays a single Steps list with a Camp field, which is what keeps the
accept / hand-in / snapshot logic untouched.
"""

import os
import re
import sys

QUEST_XML = r"D:\Godswar Origin\Localization\en_us\Settings\Sys\Quest.xml"
TEXT_DIR = r"D:\Godswar Origin\Localization\en_us\Text\Quest"
PUBLISHED_NPCS = r"D:\Godswar Origin\npc-translation\published-npcs.txt"
OUTPUT = (r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
          r"\StarterQuestChain.cs")

SPARTA_CAMP = "Sparta"
ATHENS_CAMP = "Athens"

# Regions the client gives one camp or the other. Compared as key prefixes, so
# "Sparta_Newbie" belongs to Sparta and "Athens_Newbie" to Athens.
SPARTA_REGIONS = ("Sparta_", "Peloponnese_", "Nemea_", "Argolis_", "Derveni_")
ATHENS_REGIONS = ("Athens_", "Marathon_", "Parnitha_", "Megara_", "Plataea_")

# The Sparta tutorials the server already modelled. They keep priority within
# their level so the progression a character is on stays in the same order; the
# Athens camp's copies are derived from them by the +1000 mirror below, which is
# how the client pairs the two.
TUTORIAL = [
    518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532,
    533, 534, 537, 538, 539, 543, 545, 546, 547, 548, 549, 550, 551, 552,
]

# The quest id distance between a Sparta quest and its Athens mirror.
MIRROR = 1000

REWARD = re.compile(r"(Exp|TP|Silver|Gold|BindGold)\s*:\s*(-?\d+)",
                    re.IGNORECASE)
APPEND = re.compile(r"Append\s*\{(?P<body>.*?)\}", re.DOTALL)
END_TEXT = re.compile(r"EndText\s*\{(?P<body>.*?)\}", re.DOTALL)


def read_text(quest_id):
    path = os.path.join(TEXT_DIR, f"{quest_id}.dat")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le", errors="replace")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", errors="replace")
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("gb18030", errors="replace")


def rewards(quest_id):
    text = read_text(quest_id)
    if not text:
        return (0, 0, 0, 0)
    block = APPEND.search(text) or END_TEXT.search(text)
    if block is None:
        return (0, 0, 0, 0)
    values = {"exp": 0, "tp": 0, "silver": 0, "gold": 0}
    for key, value in REWARD.findall(block.group("body")):
        name = key.lower()
        if name == "exp":
            values["exp"] = int(value)
        elif name == "tp":
            values["tp"] = int(value)
        elif name == "silver":
            values["silver"] = int(value)
        elif name == "gold":
            values["gold"] = int(value)
    return (values["exp"], values["tp"], values["silver"], values["gold"])


def quest_rows():
    rows = {}
    with open(QUEST_XML, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = re.match(r'\s*<Quest(\d+)\s', line)
            if not match:
                continue
            rows[int(match.group(1))] = dict(
                re.findall(r'(\w+)="([^"]*)"', line))
    return rows


def published_npcs():
    """The npc keys the server actually places, in the order they were listed."""
    keys = set()
    if os.path.exists(PUBLISHED_NPCS):
        with open(PUBLISHED_NPCS, "r", encoding="utf-8-sig") as handle:
            for line in handle:
                key = line.strip()
                if key:
                    keys.add(key)
    return keys


def camp_of(quest_id, row):
    keys = [row.get("GiverName", ""), row.get("ResponderName", "")]
    if any(key.startswith(ATHENS_REGIONS) for key in keys if key):
        return ATHENS_CAMP
    if any(key.startswith(SPARTA_REGIONS) for key in keys if key):
        return SPARTA_CAMP
    # A region both camps visit: the client keeps its two copies 1000 apart.
    return ATHENS_CAMP if quest_id > MIRROR else SPARTA_CAMP


def select(rows, npcs):
    """The chain rows, split by camp, each camp in its own order."""
    tutorials = {quest_id: index for index, quest_id in enumerate(TUTORIAL)}
    athens_tutorials = set()
    for quest_id in TUTORIAL:
        mirror = quest_id + MIRROR
        if mirror in rows and camp_of(mirror, rows[mirror]) == ATHENS_CAMP:
            athens_tutorials.add(mirror)

    skipped = []
    chosen = []
    for quest_id, row in rows.items():
        giver = row.get("GiverName", "")
        responder = row.get("ResponderName", "")
        if "_" not in giver:
            skipped.append((quest_id, "started by an item, not an npc"))
            continue
        if npcs and (giver not in npcs or
                     (responder and "_" in responder and
                      responder not in npcs)):
            skipped.append((quest_id, "its npc is not published"))
            continue
        try:
            level = int(row.get("MinLevel", "0"))
        except ValueError:
            level = 0
        camp = camp_of(quest_id, row)
        if camp == SPARTA_CAMP:
            rank = tutorials.get(quest_id, len(tutorials))
        else:
            rank = next(
                (index for index, mirror in enumerate(sorted(athens_tutorials))
                 if mirror == quest_id),
                len(tutorials))
        chosen.append((quest_id, camp, level, rank, giver, responder))

    ordered = {}
    for camp in (SPARTA_CAMP, ATHENS_CAMP):
        rows_of_camp = [item for item in chosen if item[1] == camp]
        rows_of_camp.sort(key=lambda item: (
            0 if item[3] < len(tutorials) else 1, item[3], item[2], item[0]))
        ordered[camp] = rows_of_camp
    return ordered, skipped


def emit(ordered):
    lines = []
    lines.append("namespace Godswar.Server.Domain.World.Content;")
    lines.append("")
    lines.append("/// <summary>")
    lines.append("/// The starter quest chains of both camps, derived from the client's")
    lines.append("/// own <c>Settings/Sys/Quest.xml</c> and <c>Text/Quest/&lt;id&gt;.dat</c>.")
    lines.append("/// </summary>")
    lines.append("/// <remarks>")
    lines.append("/// Generated by <c>tools/gen_sparta_quest_chain.py</c>; do not edit by")
    lines.append("/// hand. Every quest an npc hands out is here, split into the two camps")
    lines.append("/// the client ships in parallel: the Sparta rows and the Athens rows")
    lines.append("/// mirror each other 1000 quest ids apart, so each camp keeps its own")
    lines.append("/// order - its tutorials first, then by level - and its own next-quest")
    lines.append("/// pointer. A Sparta character is never sent to an Athens npc.")
    lines.append("/// <para>")
    lines.append("/// A quest whose giver or responder is not an npc the server places is")
    lines.append("/// left out: the accept, hand-in and snapshot frames all carry that")
    lines.append("/// npc, and an unresolved one is what made the client fault before.")
    lines.append("/// </para>")
    lines.append("/// Rewards are the Exp / TP / Silver / Gold lines of the quest text - the")
    lines.append("/// text names no reward items, so none are emitted.")
    lines.append("/// </remarks>")
    lines.append("internal static class StarterQuestChain")
    lines.append("{")
    lines.append("    /// <summary>The Sparta camp's own chain.</summary>")
    lines.append(f'    public const string SpartaCamp = "{SPARTA_CAMP}";')
    lines.append("")
    lines.append("    /// <summary>The Athens camp's own chain.</summary>")
    lines.append(f'    public const string AthensCamp = "{ATHENS_CAMP}";')
    lines.append("")
    lines.append("    internal readonly record struct Step(")
    lines.append("        uint QuestId,")
    lines.append("        string Camp,")
    lines.append("        string GiverKey,")
    lines.append("        string ResponderKey,")
    lines.append("        uint? NextQuestId,")
    lines.append("        int Experience,")
    lines.append("        int TalentPoints,")
    lines.append("        int Silver,")
    lines.append("        int Gold);")
    lines.append("")
    lines.append("    public static IReadOnlyList<Step> Steps { get; } =")
    lines.append("    [")
    for camp in (SPARTA_CAMP, ATHENS_CAMP):
        rows_of_camp = ordered[camp]
        lines.append(f"        // ---- {camp}: {len(rows_of_camp)} quests ----")
        for index, (quest_id, _, _, _, giver, responder) in enumerate(rows_of_camp):
            following = (rows_of_camp[index + 1][0]
                         if index + 1 < len(rows_of_camp) else None)
            exp, tp, silver, gold = rewards(quest_id)
            next_text = f"{following}u" if following is not None else "null"
            lines.append(
                f'        new({quest_id}, {camp}Camp, "{giver}", "{responder}", '
                f"{next_text}, {exp}, {tp}, {silver}, {gold}),")
    lines.append("    ];")
    lines.append("")
    lines.append("    public static Step? Find(uint questId)")
    lines.append("    {")
    lines.append("        foreach (var step in Steps)")
    lines.append("        {")
    lines.append("            if (step.QuestId == questId)")
    lines.append("            {")
    lines.append("                return step;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        return null;")
    lines.append("    }")
    lines.append("")
    lines.append("    public static Step? Next(uint questId) =>")
    lines.append("        Find(questId) is { NextQuestId: { } next } ? Find(next) : null;")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main():
    rows = quest_rows()
    npcs = published_npcs()
    if not npcs:
        print(f"warning: {PUBLISHED_NPCS} is missing; every npc key is accepted")
    ordered, skipped = select(rows, npcs)

    out = sys.argv[1] if len(sys.argv) > 1 else OUTPUT
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(emit(ordered))

    print(f"wrote {out}")
    for camp in (SPARTA_CAMP, ATHENS_CAMP):
        rows_of_camp = ordered[camp]
        levels = [item[2] for item in rows_of_camp]
        levels_under_200 = [value for value in levels if value < 200]
        print(f"  {camp}: {len(rows_of_camp)} quests, "
              f"levels {min(levels)}-{max(levels)}, "
              f"live {len(levels_under_200)}, "
              f"first {rows_of_camp[0][0]}, last {rows_of_camp[-1][0]}")
    print(f"  skipped: {len(skipped)}")
    reasons = {}
    for quest_id, reason in skipped:
        reasons.setdefault(reason, []).append(quest_id)
    for reason, quest_ids in reasons.items():
        print(f"    {reason}: {len(quest_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
