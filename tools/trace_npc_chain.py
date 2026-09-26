"""Print the full NPC interaction chain for one farm NPC.

Groups every packet that belongs to one dialog session - the client's 10067
click, the server's 10067 answer, the 10068 page requests, every 10069 action
and every 10070 answer - so the click-to-reply structure of a chain is visible
instead of just the reply values.
"""

import re
import struct
import sys

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

NPCS = [int(x) for x in sys.argv[1:]] or [5615, 5616, 5617]
WATCH = {10067, 10068, 10069, 10070, 10071, 10073, 10117, 10252, 10239}

SCRIPT_NAMES = {}

pending = None
session = None
session_npc = None
out = []

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
            if opcode in WATCH:
                direction = pending.group("dir")
                clock = pending.group("ts")[11:23]
                detail = ""
                if opcode == 10067 and direction == "C->S":
                    npc = int.from_bytes(frame[4:8], "little")
                    detail = f"click npc={npc}"
                    session_npc = npc if npc in NPCS else None
                    session = len(out) if session_npc else None
                elif opcode == 10067 and direction == "S->C":
                    npc = int.from_bytes(frame[4:8], "little")
                    tail = frame[16:]
                    nul = tail.find(b"\x00")
                    script = tail[:nul if nul >= 0 else len(tail)].decode()
                    detail = (f"open npc={npc} hdr8={int.from_bytes(frame[8:12], 'little')} "
                              f"hdr12={int.from_bytes(frame[12:16], 'little')} script={script}")
                    if npc in NPCS:
                        session_npc = npc
                        session = len(out)
                elif opcode == 10068:
                    detail = f"page-request npc={int.from_bytes(frame[4:8], 'little')}"
                elif opcode == 10069:
                    npc = int.from_bytes(frame[4:8], 'little')
                    dialog = struct.unpack_from("<i", frame, 8)[0]
                    sub = struct.unpack_from("<i", frame, 20)[0] if length >= 24 else -1
                    args = [struct.unpack_from("<i", frame, i)[0]
                            for i in range(24, min(length, 56), 4)]
                    detail = (f"action npc={npc} dialog={dialog} sub={sub} "
                              f"args={args}")
                elif opcode == 10070:
                    npc = int.from_bytes(frame[4:8], 'little')
                    dialog = struct.unpack_from("<i", frame, 8)[0]
                    subs = [struct.unpack_from("<i", frame, i)[0]
                            for i in range(12, length - 3, 4)]
                    detail = f"answer npc={npc} dialog={dialog} subs={subs}"
                elif opcode == 10071:
                    detail = f"SHOP len={length} head={frame[:24].hex().upper()}"
                    subs = [struct.unpack_from("<i", frame, i)[0]
                            for i in range(8, min(length, 40), 4)]
                    detail += f" ints={subs}"
                else:
                    detail = f"op{opcode} len={length} head={frame[:20].hex().upper()}"
                out.append((clock, direction, opcode, detail,
                            session if session is not None else -1))
            offset += length
        pending = None

for clock, direction, opcode, detail, group in out:
    print(f"{clock} {direction} {opcode:>5}  {detail}")
