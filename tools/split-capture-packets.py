"""Split the capture log's clear chunks into individual packets.

The proxy logs one CLEAR line per captured chunk, and a chunk can hold several
protocol frames, so the header printed on the log line only describes the first
one. Walking each chunk with the protocol's own framing (u16 length including
the header, u16 opcode) yields the real packet list, which is what the server's
own send list has to be diffed against.
"""

import re
import sys
from collections import Counter, defaultdict

LOG = (r"D:\Godswar-Reborn-main\tools\Godswar.CaptureProxy\bin\Release"
       r"\net10.0\captures\godswar-proxy-20260922-001042.log")

LINE = re.compile(
    r"^\S+ (LOGIN|GAME) (S->C|C->S) bytes=(\d+) .*? opcode=(\d+)")


def main():
    packets = []
    with open(LOG, "r", encoding="utf-8", errors="replace") as handle:
        pending = None
        for line in handle:
            line = line.rstrip("\n")
            match = LINE.match(line)
            if match:
                pending = (match.group(1), match.group(2), int(match.group(3)))
                continue
            if pending and line.startswith("CLEAR "):
                payload = bytes.fromhex(line[6:].strip())
                channel, direction, _ = pending
                offset = 0
                while offset + 4 <= len(payload):
                    length = int.from_bytes(payload[offset:offset + 2], "little")
                    opcode = int.from_bytes(payload[offset + 2:offset + 4], "little")
                    if length < 4 or offset + length > len(payload):
                        break
                    packets.append((channel, direction, opcode, length,
                                    payload[offset:offset + length]))
                    offset += length
                pending = None

    print(f"{len(packets)} framed packets")
    summary = Counter((d, o, l) for _, d, o, l, _ in packets)
    print("\n=== S->C ===")
    for (direction, opcode, length), count in sorted(
            summary.items(), key=lambda item: (item[0][0], item[0][1])):
        if direction == "S->C":
            print(f"  opcode {opcode:<6} len {length:<6} x{count}")
    print("\n=== C->S ===")
    for (direction, opcode, length), count in sorted(
            summary.items(), key=lambda item: (item[0][0], item[0][1])):
        if direction == "C->S":
            print(f"  opcode {opcode:<6} len {length:<6} x{count}")

    print("\n=== every 10043 payload ===")
    for channel, direction, opcode, length, payload in packets:
        if opcode == 10043:
            print(f"{channel} {direction} len={length}")
            print("  " + payload.hex())
    return 0


if __name__ == "__main__":
    sys.exit(main())
