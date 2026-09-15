"""Attribute every NPC click to a name, and every window to the click that caused it.

Reads the capture in local time: each C2S 10067 click with the npc's identity,
then the frames the server sent in the seconds after it - the function menus and
the window frames (window id plus the label the server put in them). That is what
tells "the mall" and "the wishing pool" apart: which npc each click named, and
which window each click produced.

Usage: python tools/trace_npc_clicks.py ["YYYY-MM-DD HH:MM:SS local"] [seconds]
"""

import struct
import subprocess
import sys

DEFAULT_SINCE = "2026-09-14 06:40:00"
WINDOW = 12

CLICKS = (
    "SELECT captured_at AT TIME ZONE 'Asia/Shanghai', "
    "encode(clear_bytes,'hex') FROM packet_transactions "
    "WHERE opcode = 10067 AND direction = 'C2S' "
    "AND captured_at AT TIME ZONE 'Asia/Shanghai' >= '{since}' "
    "ORDER BY captured_at;")

NEARBY = (
    "SELECT captured_at AT TIME ZONE 'Asia/Shanghai', direction, opcode, "
    "declared_length, encode(clear_bytes,'hex') FROM packet_transactions "
    "WHERE captured_at AT TIME ZONE 'Asia/Shanghai' >= '{start}'::timestamp "
    "AND captured_at AT TIME ZONE 'Asia/Shanghai' <= "
    "('{start}'::timestamp + interval '{window} seconds') "
    "AND opcode NOT IN (10015, 10194, 10016, 10017, 10020, 10024, 10312, "
    "10023, 10339, 10077, 10080, 10022, 10297, 10309, 10035) "
    "ORDER BY captured_at;")

NPCS = ("SELECT npc_key, template_key, map_id, pos_x, pos_z FROM "
        "npc_spawn_definitions WHERE interaction_id = {npc};")

CAPTURE_DIR = r"D:\Godswar Origin\npc-translation"
SEEDS = (r"D:\Godswar-Reborn-main\src\Godswar.Server\State"
         r"\NpcTemplateSeed.Generated.cs")


def captured_objects():
    """(map, objectId) -> (template, x, z) exactly as the reference sent it."""
    import os
    import re
    table = {}
    for name in os.listdir(CAPTURE_DIR):
        match = re.match(r"captured-npcs-map(\d+)\.txt$", name)
        if not match:
            continue
        map_id = int(match.group(1))
        with open(os.path.join(CAPTURE_DIR, name), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                parts = line.strip().split("|")
                if len(parts) == 6:
                    table[(map_id, int(parts[0]))] = (
                        parts[1], float(parts[3]), float(parts[4]))
    return table


def client_names():
    """The client's own display name for an appearance template."""
    import re
    names = {}
    text = open(SEEDS, encoding="utf-8").read()
    for match in re.finditer(
            r'new\("([A-Za-z0-9_]+)", "[A-Za-z0-9_]+", "[A-Za-z0-9_]+", '
            r'"([^"]+)", \(short\)\d+', text):
        names[match.group(1)] = match.group(2)
    return names


def query(sql):
    return subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True).stdout


def npc_identity(npc, objects, names, map_id=1):
    """What the reference placed at this id, and what the client calls it."""
    captured = objects.get((map_id, npc))
    if captured is None:
        for (other_map, other_id), value in objects.items():
            if other_id == npc:
                captured = value
                map_id = other_map
                break
    if captured is None:
        return "(not among the captured objects)"
    template, x, z = captured
    return (f"template {template} = \"{names.get(template, '?')}\" "
            f"at ({x:.1f}, {z:.1f}) map {map_id}")



def board_label(payload):
    """The 10021 window's id and the label the server put in it."""
    if len(payload) < 24:
        return ""
    window = struct.unpack_from("<I", payload, 0)[0]
    label = payload[8:24].split(b"\0")[0].decode("ascii", "replace")
    return f"window={window} label={label!r}"


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SINCE
    window = sys.argv[2] if len(sys.argv) > 2 else str(WINDOW)
    objects = captured_objects()
    names = client_names()
    clicks = []
    for line in query(CLICKS.format(since=since)).splitlines():
        if "|" not in line:
            continue
        when, hexed = line.split("|")
        data = bytes.fromhex(hexed)
        clicks.append((when.strip(), struct.unpack_from("<I", data, 4)[0]))
    if not clicks:
        print(f"no client npc clicks after {since} (local)")
        return 0

    print(f"npc clicks after {since} (local time):")
    for when, npc in clicks:
        print(f"  {when}  npc={npc}  {npc_identity(npc, objects, names)}")

    for when, npc in clicks:
        print()
        print(f"--- what npc {npc} produced at {when} "
              f"(+{window}s, quiet frames hidden)")
        for line in query(
                NEARBY.format(start=when, window=window)).splitlines():
            parts = line.split("|")
            if len(parts) != 5 or not parts[2].strip():
                continue
            at, direction, opcode, length, hexed = parts
            payload = bytes.fromhex(hexed)[4:]
            if opcode in ("10021", "10201", "10248", "10199"):
                words = " ".join(
                    str(struct.unpack_from("<I", payload, off)[0])
                    for off in range(0, min(len(payload), 12), 4))
                print(f"    {at[:19]} {direction} {opcode:>5} len={length:>5} "
                      f"head=[{words}] {board_label(payload) if opcode == '10021' else ''}")
            elif opcode in ("10067", "10068", "10069", "10070", "10279",
                            "10280", "10117"):
                words = " ".join(
                    str(struct.unpack_from("<i", payload, off)[0])
                    for off in range(0, min(len(payload), 20), 4))
                print(f"    {at[:19]} {direction} {opcode:>5} len={length:>5} "
                      f"words=[{words}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
