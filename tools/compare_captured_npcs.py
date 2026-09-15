"""Compare the captured NPC objects with the rows the server publishes.

The capture is what the reference server actually sent; the published rows are
what we wrote from the client's ini. The report is the work list: which npc keys
differ in their appearance word (and by how much), which ids differ, and which
captured npcs we have no row for.
"""
import collections
import subprocess
import sys

CAPTURE = r"D:\Godswar Origin\npc-translation\captured-npcs-map{map}.txt"

SQL = ("SELECT npc_key, template_key, object_id, interaction_id, "
       "appearance_type, pos_x, pos_z, facing FROM npc_spawn_definitions "
       "WHERE map_id = {map};")


def published(map_id):
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c",
         SQL.format(map=map_id)],
        capture_output=True, text=True, check=True).stdout
    by_template = {}
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 8:
            continue
        by_template[parts[1]] = {
            "npc_key": parts[0],
            "object_id": int(parts[2]),
            "interaction_id": int(parts[3]),
            "appearance": int(parts[4]),
            "x": float(parts[5]),
            "z": float(parts[6]),
            "facing": float(parts[7]),
        }
    return by_template


def captured(map_id):
    rows = {}
    for line in open(CAPTURE.format(map=map_id), encoding="utf-8"):
        if line.startswith("#"):
            continue
        object_id, template, low, x, z, facing = line.strip().split("|")
        rows[template] = {
            "object_id": int(object_id),
            "appearance": int(low),
            "x": float(x),
            "z": float(z),
            "facing": float(facing),
        }
    return rows


def main():
    map_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mine = published(map_id)
    theirs = captured(map_id)
    print(f"map {map_id}: captured {len(theirs)}, published {len(mine)}")

    appearance = collections.Counter()
    ids = collections.Counter()
    shifted = []
    missing = []
    for template, caps in sorted(theirs.items()):
        row = mine.get(template)
        if row is None:
            missing.append((template, caps["object_id"]))
            continue
        appearance[(row["appearance"], caps["appearance"])] += 1
        ids[caps["object_id"] - row["object_id"]] += 1
        shifted.append((row["npc_key"], template,
                        row["object_id"], caps["object_id"],
                        hex(row["appearance"]), hex(caps["appearance"])))

    print("appearance (published -> captured):")
    for (ours, theirs_low), count in sorted(appearance.items()):
        print(f"    {hex(ours):>7} -> {hex(theirs_low):<7} {count}")
    print(f"id differences: {dict(ids)}")
    print(f"captured npcs with no published row: {len(missing)}")
    for template, object_id in missing[:10]:
        print(f"    {template} (captured id {object_id})")
    print()
    print("first rows:")
    for row in shifted[:12]:
        print(f"    {row[0]:<12} {row[2]:>7} -> {row[3]:<7} "
              f"{row[4]:>7} -> {row[5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
