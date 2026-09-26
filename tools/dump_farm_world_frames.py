"""Dump every world-object frame in one time window of the farm capture.

10020 carries a single object's appearance, 10024 carries a list of object ids.
Both are how the reference server told the client which NPCs stand on a map, so
this prints them in order with the decoded fields.
"""

import re
import struct
import sys

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

start = sys.argv[1] if len(sys.argv) > 1 else "21:02:50"
end = sys.argv[2] if len(sys.argv) > 2 else "21:03:15"

pending = None
clock = ""
with open(LOG, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.rstrip("\n")
        match = HEADER.match(line)
        if match:
            pending = match
            clock = match.group("ts")[11:19]
            continue
        if pending is None or not line.startswith("CLEAR "):
            continue
        if not (start <= clock <= end):
            pending = None
            continue
        payload = bytes.fromhex(line[6:].strip())
        offset = 0
        while offset + 4 <= len(payload):
            length = int.from_bytes(payload[offset:offset + 2], "little")
            opcode = int.from_bytes(payload[offset + 2:offset + 4], "little")
            if length < 4 or offset + length > len(payload):
                break
            frame = payload[offset:offset + length]
            if opcode == 10020 and length >= 48:
                packed = struct.unpack_from("<I", frame, 4)[0]
                object_id = struct.unpack_from("<I", frame, 8)[0]
                x = struct.unpack_from("<f", frame, 28)[0]
                z = struct.unpack_from("<f", frame, 36)[0]
                facing = struct.unpack_from("<f", frame, 40)[0]
                tail = frame[44:]
                nul = tail.find(b"\x00")
                template = tail[:nul if nul >= 0 else len(tail)].decode(
                    "ascii", "replace")
                print(f"{pending.group('ts')[11:23]} {pending.group('dir')} "
                      f"10020 map={packed >> 16} appear={packed & 0xFFFF} "
                      f"obj={object_id} x={x:.2f} z={z:.2f} f={facing:.2f} "
                      f"tpl={template}")
            elif opcode == 10024:
                ids = [struct.unpack_from("<I", frame, i)[0]
                       for i in range(8, len(frame) - 3, 4)]
                print(f"{pending.group('ts')[11:23]} {pending.group('dir')} "
                      f"10024 len={length} ids={[i for i in ids if i != 0]}")
            offset += length
        pending = None
