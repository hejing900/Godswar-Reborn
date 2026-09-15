"""Compare every hard-coded (npc key, interaction id) pair with the published data.

CapitalNpcServiceProtocol, WarehouseNpcProtocol, the transporter and arena
protocols all identify an npc by its key *and* a literal interaction id. If the
published spawn data uses a different id for that key, the pair never resolves,
the dialog handler falls through every branch and the client is sent nothing -
which is what "the npc cannot be opened" looks like.
"""
import collections
import re
import subprocess
import sys

SOURCES = [
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
    r"\CapitalNpcServiceProtocol.cs",
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
    r"\WarehouseNpcProtocol.cs",
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Domain\World\Content"
    r"\DuelArenaCapturedTransportProtocol.cs",
]

PAIR = re.compile(r'\("([A-Za-z0-9_]+)",\s*(\d+)u?\)')


def catalog():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c",
         "SELECT npc_key, object_id, map_id FROM npc_spawn_definitions;"],
        capture_output=True, text=True, check=True).stdout
    table = {}
    for line in out.splitlines():
        if "|" in line:
            key, object_id, map_id = line.split("|")
            table[key.strip()] = (int(object_id), int(map_id))
    return table


def main():
    known = catalog()
    pairs = collections.OrderedDict()
    for path in SOURCES:
        try:
            text = open(path, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"missing: {path}")
            continue
        for key, object_id in PAIR.findall(text):
            pairs.setdefault(key, set()).add(int(object_id))

    mismatched = []
    unknown = []
    for key, ids in pairs.items():
        if key not in known:
            unknown.append((key, sorted(ids)))
            continue
        actual = known[key][0]
        if actual not in ids:
            mismatched.append((key, sorted(ids), actual, known[key][1]))

    print(f"hard-coded npc pairs: {len(pairs)}")
    print(f"keys the published data does not carry: {len(unknown)}")
    for key, ids in unknown:
        print(f"  {key} (code expects {ids})")
    print(f"keys whose published id differs from the code: {len(mismatched)}")
    for key, ids, actual, map_id in mismatched:
        print(f"  {key}: code expects {ids}, published {actual} (map {map_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
