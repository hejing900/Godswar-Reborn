"""Detect the player's map from a proxy capture and dump the frames per map.

The stock 10019 (enter-main) frame carries the character's current map byte at
frame offset 45: the name field is 32 bytes wide at offset 8, the six attribute
bytes follow it, and the map byte is the seventh. Walking the capture and
switching map every time a 10019 arrives therefore splits a multi-map session
into the per-map frame streams the reference server actually sent.
"""

import argparse
import re

HEADER = re.compile(
    r"^(?P<ts>\S+?) (?P<channel>LOGIN|GAME) (?P<dir>S->C|C->S) "
    r"bytes=(?P<bytes>\d+).*?opcode=(?P<opcode>\d+)")

MAP_BYTE_OFFSET = 45


def frames(log_path, start, end):
    pending = None
    clock = ""
    with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            match = HEADER.match(line)
            if match:
                pending = match
                clock = match.group("ts")[11:16]
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
                yield (pending.group("ts"), pending.group("dir"), opcode,
                       payload[offset:offset + length])
                offset += length
            pending = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--from", dest="start", default="00:00")
    parser.add_argument("--to", dest="end", default="23:59")
    parser.add_argument("--dump-map", type=int, default=None)
    parser.add_argument("--opcodes", default=None)
    parser.add_argument("--max-bytes", type=int, default=48)
    args = parser.parse_args()

    wanted = None
    if args.opcodes:
        wanted = {int(part) for part in args.opcodes.split(",")}

    current = None
    counts = {}
    for ts, direction, opcode, body in frames(args.log, args.start, args.end):
        if opcode == 10019 and direction == "S->C" and len(body) > MAP_BYTE_OFFSET:
            current = body[MAP_BYTE_OFFSET]
            print(f"{ts}  === map -> {current} "
                  f"name={body[8:40].split(bytes([0]))[0].decode(errors='replace')}")
            continue
        counts[(current, direction, opcode)] = \
            counts.get((current, direction, opcode), 0) + 1
        if args.dump_map is None or current != args.dump_map:
            continue
        if wanted is not None and opcode not in wanted:
            continue
        hexed = body[:args.max_bytes].hex().upper()
        runs = []
        run = bytearray()
        for index, byte in enumerate(body):
            if 32 <= byte < 127:
                run.append(byte)
            else:
                if len(run) >= 4:
                    runs.append(f"+{index - len(run)}:'{run.decode()}'")
                run = bytearray()
        if len(run) >= 4:
            runs.append(f"+{len(body) - len(run)}:'{run.decode()}'")
        suffix = ("  " + " ".join(runs)) if runs else ""
        print(f"{ts} {direction} op={opcode} len={len(body)} {hexed}"
              f"{'' if len(body) <= args.max_bytes else '...'}{suffix}")

    if args.dump_map is None:
        print("\n=== frames per map ===")
        for (map_id, direction, opcode), count in sorted(
                counts.items(), key=lambda item: (item[0][0] is None,
                                                  item[0][0], item[0][1],
                                                  item[0][2])):
            print(f"map={map_id} {direction} op={opcode} x{count}")


if __name__ == "__main__":
    main()
