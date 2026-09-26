"""Dump the full byte layout of the quartermaster's captured shop frame.

The frame is the reference server's own 10071 catalogue for the Lelantine Farm
quartermaster, so every field below is captured data rather than invention.
"""

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
            if (opcode == 10071 and length == 892
                    and struct.unpack_from("<I", frame, 8)[0] == 5616):
                print(f"captured at {pending.group('ts')} len={length}")
                print("hex:")
                for i in range(0, len(frame), 16):
                    chunk = frame[i:i + 16]
                    print(f"  +{i:04d}  {chunk.hex(' ').upper()}")
                print("\nheader ints:")
                for i in range(4, 20, 4):
                    print(f"  +{i} = {struct.unpack_from('<i', frame, i)[0]}")
                print("\nrecord area as ints (first 16):")
                for i in range(16, min(length, 80), 4):
                    print(f"  +{i} = {struct.unpack_from('<i', frame, i)[0]}")
                print("\nascii runs:")
                run = bytearray()
                for index, byte in enumerate(frame):
                    if 32 <= byte < 127:
                        run.append(byte)
                    else:
                        if len(run) >= 3:
                            print(f"  +{index - len(run)}: {run.decode()}")
                        run = bytearray()
                raise SystemExit
            offset += length
        pending = None
