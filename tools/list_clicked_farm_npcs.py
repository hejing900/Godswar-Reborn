"""List every NPC id the client actually clicked, with the script it was answered by.

C2S 10067 carries the clicked npc's object id as a bare dword; the S->C 10067
answer names the client script. Pairing them shows which object ids the
reference server really placed on the map being played.
"""

import re

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

pending = None
last_request = None
rows = []

with open(LOG, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.rstrip("\n")
        match = HEADER.match(line)
        if match:
            pending = match
            continue
        if pending is None or not line.startswith("CLEAR "):
            continue
        payload = bytes.fromhex(line[6:].strip())
        offset = 0
        while offset + 4 <= len(payload):
            length = int.from_bytes(payload[offset:offset + 2], "little")
            opcode = int.from_bytes(payload[offset + 2:offset + 4], "little")
            if length < 4 or offset + length > len(payload):
                break
            frame = payload[offset:offset + length]
            if opcode == 10067 and pending.group("dir") == "C->S":
                last_request = (pending.group("ts"), int.from_bytes(
                    frame[4:8], "little"))
            elif opcode == 10067 and pending.group("dir") == "S->C":
                npc_id = int.from_bytes(frame[4:8], "little")
                tail = frame[16:]
                nul = tail.find(b"\x00")
                script = tail[:nul if nul >= 0 else len(tail)].decode(
                    "ascii", "replace")
                rows.append((pending.group("ts"), npc_id, script))
            offset += length
        pending = None

print(f"{'answered at':<30} {'npcId':>7}  script")
seen = set()
for ts, npc_id, script in rows:
    if npc_id in seen:
        continue
    seen.add(npc_id)
    print(f"{ts:<30} {npc_id:>7}  {script}")

print(f"\ndistinct clicked npcs: {len(seen)}")
farm = sorted(n for _, n, s in rows if s.startswith("Lelantine_Farm"))
print("farm npc ids in click order:",
      sorted({n for _, n, s in rows if s.startswith("Lelantine_Farm")}))
