"""Locate which protocol frame actually carries the Lelantine Farm templates.

A capture CLEAR line is a chunk of concatenated frames, so a raw hex search can
match across a frame boundary. This walks each chunk with the protocol's own
framing and reports the frame that truly contains the template bytes.
"""

import re
import sys

LOG = r"D:\Godswar-Reborn-main\captures\godswar-proxy-20260926-202040.log"
NEEDLES = [
    b"Lelantine_Farm",
    b"Lelantine_Farm_003_WarField3",
    b"Lelantine_Farm_004_WarField2",
    b"Lelantine_Farm_005_WarField1",
    b"Lelantine_Farm_001_Male8",
    b"Lelantine_Farm_002_WarField4",
    b"Lelantine_Farm_006_WarField3",
    b"Lelantine_Farm_007_WarField2",
    b"Lelantine_Farm_008_WarField1",
]

HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

pending = None
found = 0
chunk_index = 0

with open(LOG, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.rstrip("\n")
        match = HEADER.match(line)
        if match:
            pending = match
            continue
        if pending is None or not line.startswith("CLEAR "):
            continue
        chunk_index += 1
        payload = bytes.fromhex(line[6:].strip())
        offset = 0
        while offset + 4 <= len(payload):
            length = int.from_bytes(payload[offset:offset + 2], "little")
            opcode = int.from_bytes(payload[offset + 2:offset + 4], "little")
            if length < 4 or offset + length > len(payload):
                break
            frame = payload[offset:offset + length]
            for needle in NEEDLES:
                if needle in frame:
                    found += 1
                    print(f"{pending.group('ts')} {pending.group('dir')} "
                          f"opcode={opcode} len={length} needle={needle.decode()}")
                    # printable strings inside the frame
                    runs = []
                    run = bytearray()
                    for index, byte in enumerate(frame):
                        if 32 <= byte < 127:
                            run.append(byte)
                        else:
                            if len(run) >= 4:
                                runs.append(f"+{index - len(run)}:'{run.decode()}'")
                            run = bytearray()
                    if len(run) >= 4:
                        runs.append(f"+{len(frame) - len(run)}:'{run.decode()}'")
                    if runs:
                        print("    ascii: " + " ".join(runs[:8]))
                    print("    head: " + frame[:48].hex().upper())
                    break
            offset += length
        pending = None

print(f"\nmatched frames: {found}")
