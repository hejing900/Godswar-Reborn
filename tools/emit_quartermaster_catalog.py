"""Emit the quartermaster's captured 10071 catalogue frame as base64+gzip.

The output is pasted into the server as an embedded catalogue source, exactly
like the capital vendor catalogues already stored there, so the farm shop ships
the reference server's own bytes rather than a re-authored list.
"""

import base64
import gzip
import re
import struct

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

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
            if (opcode == 10071 and length >= 16
                    and struct.unpack_from("<I", frame, 4)[0] == 5616):
                print(f"captured at {pending.group('ts')}")
                print(f"frame length: {len(frame)}")
                print(f"category: {frame[8]}  currency: {frame[9]}  "
                      f"count: {frame[10]}  fresh: {frame[11]}")
                compressed = gzip.compress(frame, mtime=0, compresslevel=9)
                print(f"gzip length: {len(compressed)}  "
                      f"base64 length: {len(base64.b64encode(compressed))}")
                print("\nBASE64:")
                print(base64.b64encode(compressed).decode())
                print("\nPYTHON-BYTE-ARRAY:")
                print("[\n" + "\n".join(
                    "    " + ", ".join(f"0x{b:02X}" for b in
                                      frame[i:i + 12])
                    for i in range(0, len(frame), 12)) + "\n]")
                raise SystemExit
            offset += length
        pending = None

print("not found")
