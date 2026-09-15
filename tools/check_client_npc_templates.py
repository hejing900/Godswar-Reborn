"""Do the client's own files know each published npc's appearance template?

The world-object frame names a template key (Sparta_023_Male6, Athens_025_Male6).
The client resolves that key in its own Settings/Sys/NPC.INI, so a key the file
does not carry is an object the client cannot finish creating or interact with.
Sparta's city npcs came from the reference capture; every other map's came from
the ini placement catalog, so this measures how far the two really agree.
"""
import collections
import re
import subprocess
import sys

NPC_INI = r"D:\Godswar Origin\Localization\en_us\Settings\Sys\NPC.INI"

SQL = ("SELECT map_id, npc_key, template_key FROM npc_spawn_definitions "
       "ORDER BY map_id, npc_key;")


def client_sections():
    raw = open(NPC_INI, "rb").read()
    text = raw.decode(
        "utf-16-le" if raw[:2] == b"\xff\xfe" else "latin-1", errors="replace")
    return set(re.findall(r"^\s*\[([^\]]+)\]\s*$", text, re.M))


def rows():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.count("|") == 2:
            map_id, npc_key, template_key = line.split("|")
            yield int(map_id), npc_key.strip(), template_key.strip()


def main():
    sections = client_sections()
    print(f"client NPC.INI sections: {len(sections)}")
    per_map = collections.defaultdict(lambda: [0, 0])
    missing = collections.defaultdict(list)
    for map_id, npc_key, template_key in rows():
        known = template_key in sections
        per_map[map_id][0 if known else 1] += 1
        if not known:
            missing[map_id].append((npc_key, template_key))
    print(f"{'map':>4}{'known':>8}{'missing':>9}")
    for map_id in sorted(per_map):
        known, absent = per_map[map_id]
        print(f"{map_id:>4}{known:>8}{absent:>9}")
    for map_id in sorted(missing):
        print(f"map {map_id}: first missing "
              f"{missing[map_id][:6]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
