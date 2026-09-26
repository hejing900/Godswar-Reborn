"""Summarise every world object the capture sent for one map.

Groups the 10020 appearance frames by template and reports the observed count,
object-id range, and coordinate envelope, so a map's captured content can be
compared against what the server claims to publish.
"""

import re
import struct
import sys

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
TARGET_MAP = int(sys.argv[1]) if len(sys.argv) > 1 else 42

HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

pending = None
objects = {}

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
            if opcode == 10020 and length >= 48:
                packed = struct.unpack_from("<I", frame, 4)[0]
                if packed >> 16 != TARGET_MAP:
                    offset += length
                    continue
                object_id = struct.unpack_from("<I", frame, 8)[0]
                x = struct.unpack_from("<f", frame, 28)[0]
                z = struct.unpack_from("<f", frame, 36)[0]
                tail = frame[44:]
                nul = tail.find(b"\x00")
                template = tail[:nul if nul >= 0 else len(tail)].decode(
                    "ascii", "replace")
                objects[object_id] = (packed & 0xFFFF, x, z, template)
            offset += length
        pending = None

by_template = {}
for object_id, (appear, x, z, template) in objects.items():
    by_template.setdefault(template, []).append((object_id, appear, x, z))

print(f"map {TARGET_MAP}: {len(objects)} distinct objects, "
      f"{len(by_template)} distinct templates\n")
print(f"{'count':>5} {'objId min':>10} {'objId max':>10} {'appear':>7}  template")
for template, rows in sorted(by_template.items()):
    ids = [r[0] for r in rows]
    appears = sorted({r[1] for r in rows})
    print(f"{len(rows):>5} {min(ids):>10} {max(ids):>10} "
          f"{','.join(str(a) for a in appears):>7}  {template}")
