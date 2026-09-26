"""Decode the quartermaster's captured 10071 catalogue into item records.

Header (16 bytes): +0 u16 frame length, +2 u16 opcode, +4 u32 npc id,
+8 u8 category, +9 u8 currency, +10 u8 item count, +11 u8 fresh-list flag,
+12 i32 balance. Each 88-byte record starts with a u32 item id.
"""

import re
import struct

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

RECORD = 88
pending = None

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
            if opcode == 10071 and length >= 16:
                npc_id = struct.unpack_from("<I", frame, 4)[0]
                if npc_id == 5616:
                    category = frame[8]
                    currency = frame[9]
                    count = frame[10]
                    fresh = frame[11]
                    balance = struct.unpack_from("<i", frame, 12)[0]
                    print(f"captured {pending.group('ts')} len={length} "
                          f"npc={npc_id} category={category} "
                          f"currency={currency} count={count} "
                          f"fresh={fresh} balance={balance}")
                    for index in range(count):
                        base = 16 + index * RECORD
                        item_id = struct.unpack_from("<I", frame, base)[0]
                        price = struct.unpack_from("<i", frame, base + 76)[0]
                        qty = frame[base + 27]
                        print(f"  [{index:>2}] item={item_id:<8} "
                              f"price={price:<10} qtyByte={qty} "
                              f"record={frame[base:base + RECORD].hex().upper()}")
                    raise SystemExit
            offset += length
        pending = None

print("no quartermaster catalogue frame found")
