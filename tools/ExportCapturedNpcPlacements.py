"""Export captured NPC placements as the text files the placement generator reads.

`tools/gen_captured_npc_placements.py` reads `captured-npcs-map<N>.txt` from the
client's `npc-translation` folder and turns them into
`CapturedNpcPlacements.Generated.cs`. Those text files were hand-produced from
earlier captures, so a new capture could not feed the pipeline without another
manual pass.

This closes that gap: it reads `npc_spawn_packets` (the capture proxy's landing
table) and writes the same format, one file per map. Every field the format
needs is already in the stored frame:

    low    = (object type >> 16), the appearance word the reference sent
             (0x111 Athens-style, 0x211 Sparta-style)
    x, z   = frame offsets +28 and +36 (little-endian float32)
    facing = frame offset +40 (little-endian float32)
    key    = the template key up to its trailing model segment

Usage:
    python tools/ExportCapturedNpcPlacements.py --dry-run
    python tools/ExportCapturedNpcPlacements.py --maps 1,2,11
"""

import argparse
import os
import re
import struct
import subprocess
import sys

CONTAINER = "godswar-postgres"
DATABASE = "godswar"
USER = "godswar"
OUTPUT_DIR = r"D:\Godswar Origin\npc-translation"


def npc_key_of(template):
    """The NPC key is the template key up to its trailing model segment.

    `Athens_012_MaleMerchant3` -> `Athens_012`, but the scene key itself may
    contain underscores and non-numeric segments, so the key cannot be matched
    with a `word_digits` pattern: `Athens_Newbie_001_MaleVillager2` and
    `Marathon_All_013_FemMale7` have to yield `Athens_Newbie_001` and
    `Marathon_All_013`. Verified against all 143 published rows of maps 1, 2
    and 11: taking everything before the final underscore matches the table's
    own npc_key exactly.
    """
    head, separator, _ = template.rpartition("_")
    return head if separator else None

QUERY = """
SELECT map_id, template_key, pos_x, pos_z, encode(clear_bytes, 'hex')
FROM npc_spawn_packets
WHERE map_id = ANY(ARRAY[{maps}]::smallint[])
ORDER BY map_id, template_key;
"""

HEADER = "# objectId|template|appearance|x|z|facing"


def query_rows(maps):
    sql = QUERY.format(maps=",".join(str(m) for m in maps))
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-X", "-q", "-A", "-t", "-F", "\t",
         "-v", "ON_ERROR_STOP=1", "-U", USER, "-d", DATABASE, "-c", sql],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"psql failed: {result.stderr.strip()}")
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        map_id, template, x, z, hex_bytes = line.split("\t")
        yield int(map_id), template, float(x), float(z), bytes.fromhex(hex_bytes)


def frame_fields(frame):
    """Pull objectId, appearance word and facing out of a 10020 frame.

    The appearance word is the low 16 bits of the object type word at +4
    (0x0111 Athens-style, 0x0211 Sparta-style). The next byte up is the map id
    and the one above that is the category (0x11 NPC / 0x12 monster), so the
    word must be read as a little-endian u16 rather than shifted out of the u32.
    """
    if len(frame) < 44:
        raise ValueError(f"frame is only {len(frame)} bytes")
    declared, opcode = struct.unpack_from("<HH", frame, 0)
    if declared != len(frame) or opcode != 10020:
        raise ValueError(f"not a 10020 frame (declared={declared}, opcode={opcode})")
    object_id = struct.unpack_from("<I", frame, 8)[0]
    appearance = struct.unpack_from("<H", frame, 4)[0]
    facing = struct.unpack_from("<f", frame, 40)[0]
    return object_id, appearance, facing


def read_existing(path):
    """Read a previously written capture file so older sessions are not lost.

    One capture session only sees the NPCs the player actually walked past, so
    the current session's rows must be unioned with the file already on disk
    rather than replacing it. The 2026-09-22 session, for example, holds 108 of
    Athens' city NPCs while the file from the earlier session holds 96, and the
    89 they share agree exactly - the 7 the old file has and this one does not
    would otherwise be dropped from the published placements.
    """
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            parts = line.strip().split("|")
            if len(parts) != 6:
                continue
            object_id, template, appearance, x, z, facing = parts
            key = npc_key_of(template)
            if key is not None:
                rows[key] = (int(object_id), template, int(appearance),
                             float(x), float(z), float(facing))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written without writing")
    parser.add_argument("--maps", default="",
                        help="comma-separated map ids; default is every captured map")
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    if args.maps:
        maps = [int(value) for value in args.maps.split(",") if value.strip()]
    else:
        sql = ("SELECT DISTINCT map_id FROM npc_spawn_packets ORDER BY map_id;")
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-X", "-q", "-A", "-t",
             "-U", USER, "-d", DATABASE, "-c", sql],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"psql failed: {result.stderr.strip()}")
        maps = [int(line) for line in result.stdout.split() if line.strip()]

    if not maps:
        raise SystemExit("no captured NPC map found")

    by_map = {}
    for map_id, template, x, z, frame in query_rows(maps):
        if npc_key_of(template) is None:
            continue
        object_id, appearance, facing = frame_fields(frame)
        by_map.setdefault(map_id, []).append(
            (object_id, template, appearance, x, z, facing))

    for map_id in sorted(by_map):
        session_rows = sorted(by_map[map_id])
        path = os.path.join(args.output_dir, f"captured-npcs-map{map_id}.txt")

        previous = read_existing(path)
        merged = dict(previous)
        updated = 0
        for object_id, template, appearance, x, z, facing in session_rows:
            key = npc_key_of(template)
            if key in merged:
                updated += 1
            merged[key] = (object_id, template, appearance, x, z, facing)

        rows = sorted(merged.values())
        added = len(merged) - len(previous)
        carried = len(previous) - updated
        appearance_words = {}
        for _, _, appearance, _, _, _ in rows:
            appearance_words[appearance] = appearance_words.get(appearance, 0) + 1

        print(f"map {map_id}: session {len(session_rows)} NPCs "
              f"(updated {updated}), carried over {carried}, new {added} "
              f"-> {len(rows)} total")
        print(f"    appearance { {hex(k): v for k, v in sorted(appearance_words.items())} }")
        if args.dry_run:
            print(f"    would write {path}")
            continue

        if os.path.exists(path):
            backup = path + ".bak"
            with open(path, encoding="utf-8") as handle:
                previous_text = handle.read()
            with open(backup, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(previous_text)
            print(f"    backed up existing file to {os.path.basename(backup)}")

        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(HEADER + "\n")
            for object_id, template, appearance, x, z, facing in rows:
                handle.write(f"{object_id}|{template}|{appearance}|"
                             f"{x:.4f}|{z:.4f}|{facing:.4f}\n")
        print(f"    wrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
