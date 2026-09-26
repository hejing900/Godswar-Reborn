"""Slice a proxy capture log by wall-clock window and print framed packets.

The proxy logs one `CLEAR <hex>` line per captured chunk; a chunk can hold
several protocol frames, so each chunk is re-walked with the protocol's own
framing (u16 length including the header, u16 opcode) exactly like
`split-capture-packets.py` does.

Usage:
    python tools/extract_capture_window.py --from 21:00 --to 21:10
    python tools/extract_capture_window.py --from 21:00 --to 21:10 --opcodes 10067,10069,10070
"""

import argparse
import re
import sys
from collections import Counter

HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")
STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):(\d{2})")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--from", dest="start", required=True, help="HH:MM")
    parser.add_argument("--to", dest="end", required=True, help="HH:MM")
    parser.add_argument("--opcodes", default=None,
                        help="comma separated opcode filter")
    parser.add_argument("--max-bytes", type=int, default=64,
                        help="max payload bytes rendered per frame")
    parser.add_argument("--summary", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    wanted = None
    if args.opcodes:
        wanted = {int(part) for part in args.opcodes.split(",") if part.strip()}

    frames = []
    pending = None
    with open(args.log, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            match = HEADER.match(line)
            if match:
                pending = match
                continue
            if pending is not None and line.startswith("CLEAR "):
                stamp = STAMP.match(pending.group("ts"))
                clock = stamp.group(2) if stamp else ""
                if args.start <= clock <= args.end:
                    payload = bytes.fromhex(line[6:].strip())
                    offset = 0
                    while offset + 4 <= len(payload):
                        length = int.from_bytes(payload[offset:offset + 2], "little")
                        opcode = int.from_bytes(payload[offset + 2:offset + 4], "little")
                        if length < 4 or offset + length > len(payload):
                            break
                        body = payload[offset:offset + length]
                        if wanted is None or opcode in wanted:
                            frames.append((pending.group("ts"),
                                           pending.group("dir"),
                                           opcode, length, body))
                        offset += length
                pending = None

    if args.summary:
        summary = Counter((direction, opcode) for _, direction, opcode, _, _ in frames)
        for (direction, opcode), count in sorted(summary.items()):
            print(f"{direction} {opcode:>6} x{count}")
        print(f"total {len(frames)} frames")
        return

    for ts, direction, opcode, length, body in frames:
        hexed = body[:args.max_bytes].hex().upper()
        tail = "" if length <= args.max_bytes else "..."
        ascii_runs = []
        run = bytearray()
        for index, byte in enumerate(body):
            if 32 <= byte < 127:
                run.append(byte)
            else:
                if len(run) >= 4:
                    ascii_runs.append(f"+{index - len(run)}:'{run.decode()}'")
                run = bytearray()
        if len(run) >= 4:
            ascii_runs.append(f"+{len(body) - len(run)}:'{run.decode()}'")
        suffix = ("  " + " ".join(ascii_runs)) if ascii_runs else ""
        print(f"{ts} {direction} op={opcode} len={length} {hexed}{tail}{suffix}")


if __name__ == "__main__":
    sys.exit(main())
