"""Extract every captured 10020 world-object frame for the Lelantine Farm.

Each frame is the authoritative placement record the reference server sent:
map id and appearance word at +4, object id at +8, current/max health at
+20/+24, X at +28, Y at +32, Z at +36, facing at +40, and the appearance
template name as a NUL-terminated ASCII string at +44.
"""

import re
import struct

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
NEEDLE = b"Lelantine_Farm"

HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

pending = None
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
            if opcode == 10020 and NEEDLE in frame:
                packed = struct.unpack_from("<I", frame, 4)[0]
                object_id = struct.unpack_from("<I", frame, 8)[0]
                cur_hp = struct.unpack_from("<I", frame, 20)[0]
                max_hp = struct.unpack_from("<I", frame, 24)[0]
                x = struct.unpack_from("<f", frame, 28)[0]
                y = struct.unpack_from("<f", frame, 32)[0]
                z = struct.unpack_from("<f", frame, 36)[0]
                facing = struct.unpack_from("<f", frame, 40)[0]
                name_end = frame.index(b"\x00", 44)
                template = frame[44:name_end].decode("ascii", "replace")
                rows.append((pending.group("ts"), packed >> 16, packed & 0xFFFF,
                             object_id, cur_hp, max_hp, x, y, z, facing, template))
            offset += length
        pending = None

seen = {}
for row in rows:
    seen.setdefault(row[3], row)

print(f"total farm 10020 frames: {len(rows)}  distinct object ids: {len(seen)}")
print()
print(f"{'timestamp':<30} {'map':>3} {'appear':>6} {'objectId':>8} "
      f"{'hp':>6} {'maxHp':>6} {'X':>9} {'Y':>7} {'Z':>9} {'facing':>7}  template")
for ts, map_id, appear, object_id, cur, mx, x, y, z, facing, template in sorted(
        seen.values(), key=lambda r: (r[1], r[3])):
    print(f"{ts:<30} {map_id:>3} {appear:>6} {object_id:>8} "
          f"{cur:>6} {mx:>6} {x:>9.3f} {y:>7.3f} {z:>9.3f} {facing:>7.3f}  {template}")
