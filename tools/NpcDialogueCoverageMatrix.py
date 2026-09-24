"""Coverage matrix: every spawned NPC key on every map vs. what actually answers it.

Deliberately conservative about "covered": a key counts as handled only when it appears
in a table that the dialogue dispatch consults, not merely somewhere in the source. The
dispatch order in GameClientHandler.NpcDialogOpen.cs is warehouse/manager, newbie guide,
quest page, wishing pool, scripted catalogue, duel arena, capital NPC services, the
versioned dialogue routes, and finally a bare description window; each of those owners is
listed below by the file that holds its endpoint table.

Anything left over is a real gap. The tool prints the gap grouped by map with each NPC's
own name and description so the 2.12 wording test can be applied, and writes a CSV that
can be diffed against later runs to show coverage moving to zero.
"""

import csv
import glob
import os
import re
import subprocess

REPO = r"D:\Godswar-Reborn-main"
SRC = os.path.join(REPO, "src", "Godswar.Server")
OUT = os.path.join(REPO, "artifacts", "npc-dialogue-probe-tags", "coverage.csv")
DB = "godswar_local"

# Files that own a dialogue endpoint table. A key named in one of these is answered by
# that owner; a key named anywhere else is not.
#
# Several owners match on the (key, interaction id) pair rather than the key alone, and
# the live client data has drifted for a number of Athens tuples, so the tool keeps both
# the key literals and the id literals per file and only credits a key when the file also
# names that NPC's live interaction id.
OWNERS = {
    "scripted": ["Game/ScriptedNpcDialogueCatalog.Routing.cs"],
    "quest": ["Domain/World/Content/StarterQuestChain.cs",
              "Infrastructure/WorldContent/NpcDialogueBaselineV*.cs"],
    "wishing-pool": ["Game/GameClientHandler.NpcDialogOpen.cs",
                     "Game/WishingPoolDialogueCatalog.cs"],
    "zeus": ["Game/ZeusGiftDialogueCatalog.cs", "Game/ZeusGiftSaintDialogueCatalog.cs"],
    "warehouse": ["Domain/World/Content/WarehouseNpcProtocol.cs"],
    "capital-services": ["Domain/World/Content/CapitalNpcServiceProtocol.cs",
                         "Game/ClassSuitProtocol.cs",
                         "Game/GearEnhancerProtocol.cs"],
    "instance": ["Domain/World/Content/InstanceCallerProtocol.cs"],
    "transporter": ["Domain/World/Content/TransporterProtocol.cs"],
    "guide": ["Domain/World/Content/QuestContentBaseline.cs"],
    "faction-crier": ["Application/FactionCrier/FactionCrierCommandEnvelope.cs",
                      "Application/FactionCrier/FactionCrierRewardPolicy.cs"],
    "duel-arena": ["Domain/World/Content/DuelArenaCapturedTransportProtocol.cs",
                   "Domain/World/Content/DuelArenaTransporterProtocol.cs",
                   "Domain/World/Content/DuelArenaServiceProtocol.cs",
                   "Domain/World/Content/DuelArenaExitProtocol.cs",
                   "Domain/World/Content/BattlefieldTransporterProtocol.cs"],
    "online-award": ["Domain/World/Content/OnlineAwardProtocol.cs"],
}

# Owners whose tables pair a key with an interaction id, so both must appear. The
# wishing pool and the Zeus endpoints match on the NPC key alone and stay out of this
# set, otherwise their ids being absent from the table drops a real owner.
TUPLE_OWNERS = {"warehouse", "capital-services", "instance", "transporter",
                "online-award", "duel-arena"}

# Owners that name interaction ids and no NPC key at all.
ID_ONLY_OWNERS = {"guide", "faction-crier"}

KEY = re.compile(r'"([A-Za-z][A-Za-z0-9_]*_\d{2,3}(?:_[a-z])?)"')
ID = re.compile(r"\b([45]\d{3}|5\d{4}|59\d{3}|3\d{4})\b")


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def owner_keys():
    """owner -> (npc keys, interaction ids) collected from that owner's endpoint tables."""
    result = {}
    for owner, relatives in OWNERS.items():
        keys, ids = set(), set()
        for relative in relatives:
            pattern = os.path.join(SRC, relative.replace("/", os.sep))
            for path in sorted(glob.glob(pattern)):
                text = read(path)
                keys.update(KEY.findall(text))
                ids.update(int(value) for value in ID.findall(text))
        if not keys and not ids:
            print(f"warning: owner {owner} matched no source file ({relatives})")
        result[owner] = (keys, ids)
    return result


def psql(query):
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar", "-d", DB, "-tAc", query],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode:
        raise SystemExit(done.stderr.strip()[:300])
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


SPAWNED = (
    "select s.map_id||'|'||s.npc_key||'|'||s.interaction_id||'|'||"
    " coalesce(nullif(t.display_name,''),'(no name)') "
    "from npc_spawn_definitions s "
    "left join npc_text_templates t on t.npc_key=s.npc_key and t.scene_key=s.scene_key "
    "group by 1 order by 1;"
)

DESCRIPTIONS = (
    "select npc_key||'|'||replace(replace(coalesce(description,''),E'\\n',' '),E'\\r',' ') "
    "from npc_text_templates;"
)


def main():
    owners = owner_keys()
    routed = set(psql("select distinct npc_key from npc_dialogue_bindings;"))
    owners["routed"] = (routed, set())

    descriptions = {}
    for line in psql(DESCRIPTIONS):
        key, _, text = line.partition("|")
        descriptions.setdefault(key, text)

    rows = []
    for line in psql(SPAWNED):
        map_id, key, interaction, name = (line.split("|") + ["", "", "", ""])[:4]
        answering = []
        for owner, (keys, ids) in owners.items():
            id_match = int(interaction) in ids
            key_match = key in keys
            if owner in TUPLE_OWNERS:
                hit = key_match and id_match
            elif owner in ID_ONLY_OWNERS:
                hit = id_match
            else:
                hit = key_match or id_match
            if hit:
                answering.append(owner)
        if descriptions.get(key):
            # The last branch of the open packet: any NPC with its own description text
            # opens that window, so it answers the click even with no function page.
            answering.append("description")
        rows.append({"map": map_id, "npc_key": key, "interaction_id": interaction,
                     "display_name": name, "answered_by": ",".join(sorted(answering)) or "NONE",
                     "description": descriptions.get(key, "")[:200]})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    gaps = [r for r in rows if r["answered_by"] == "NONE"]
    print(f"spawned rows : {len(rows)}   maps: {len({r['map'] for r in rows})}")
    for owner in sorted(owners):
        hit = len({r["npc_key"] for r in rows if owner in r["answered_by"].split(",")})
        print(f"  {owner:<17}: {hit:>3} of the spawned keys")
    print(f"UNANSWERED   : {len(gaps)} keys")
    by_map = {}
    for row in gaps:
        by_map.setdefault(row["map"], []).append(row)
    print("\n--- unanswered, by map ---")
    for map_id in sorted(by_map, key=int):
        names = ", ".join(f"{r['npc_key']}[{r['display_name']}]" for r in sorted(
            by_map[map_id], key=lambda r: r["npc_key"]))
        print(f"map {map_id} ({len(by_map[map_id])}): {names}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
