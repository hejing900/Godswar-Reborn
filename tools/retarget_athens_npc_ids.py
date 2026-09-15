"""Point the hard-coded Athens npc ids at the captured ones.

The capital, warehouse, transporter and arena protocols identify an npc by its
key *and* a literal interaction id. The Athens ids were taken from the client's
ini; the capture shows the reference server used a different one for most npcs,
so the literals have to move with the placement patch or the dialog the patch
fixes would stop resolving. Sparta's ids are left alone - those maps are already
published from the capture and work.

Usage: python tools/retarget_athens_npc_ids.py [--write]
"""

import importlib.util
import re
import sys

CAPTURE = r"D:\Godswar Origin\npc-translation\captured-npcs-map{map}.txt"
FILES = [
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
    r"\CapitalNpcServiceProtocol.cs",
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
    r"\WarehouseNpcProtocol.cs",
]

PAIR = re.compile(r'\("(Athens_[A-Za-z0-9_]+)",\s*(\d+)u?\)')
CONST = re.compile(
    r'(public const uint (Athens[A-Za-z0-9]*NpcId)\s*=\s*)(\d+)(u?;)')

# The named constants in WarehouseNpcProtocol stand for one npc each; the pairs
# in the other files carry their key inline.
CONST_KEYS = {
    "AthensWarehouseNpcId": "Athens_025",
    "AthensSecondaryWarehouseNpcId": "Athens_100",
    "AthensManagerNpcId": "Athens_134",
}


def captured_ids():
    ids = {}
    for map_id in (1, 2):
        try:
            handle = open(CAPTURE.format(map=map_id), encoding="utf-8")
        except FileNotFoundError:
            continue
        with handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                parts = line.strip().split("|")
                if len(parts) != 6:
                    continue
                template = parts[1]
                match = re.match(r"^([A-Za-z0-9]+_[0-9]+)_", template)
                if match:
                    ids[match.group(1)] = int(parts[0])
    return ids


def published_ids():
    """The interaction ids the server publishes, which matching uses at runtime."""
    import subprocess
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c",
         "SELECT npc_key, interaction_id FROM npc_spawn_definitions "
         "WHERE map_id IN (1, 2);"],
        capture_output=True, text=True, check=True).stdout
    ids = {}
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 2:
            ids[parts[0].strip()] = int(parts[1])
    return ids


def main():
    write = "--write" in sys.argv
    restore = "--restore" in sys.argv
    ids = published_ids() if restore else captured_ids()
    print(f"{'published' if restore else 'captured'} Athens npc ids: {len(ids)}")
    for path in FILES:
        text = open(path, encoding="utf-8").read()
        changes = []

        def swap_pair(match):
            key, old = match.group(1), int(match.group(2))
            new = ids.get(key)
            if new is None or new == old:
                return match.group(0)
            changes.append(f"  {key}: {old} -> {new}")
            return f'("{key}", {new}u)'

        text = PAIR.sub(swap_pair, text)

        def swap_const(match):
            name, old = match.group(2), int(match.group(3))
            key = CONST_KEYS.get(name)
            new = ids.get(key) if key else None
            if new is None or new == old:
                return match.group(0)
            changes.append(f"  {name} ({key}): {old} -> {new}")
            return f"{match.group(1)}{new}{match.group(4)}"

        text = CONST.sub(swap_const, text)
        if changes:
            print(f"{path.split(chr(92))[-1]}: {len(changes)} pairs")
            for line in changes:
                print(line)
        if write and changes:
            open(path, "w", encoding="utf-8", newline="\n").write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
