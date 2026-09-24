"""Dump one captured or shipped merchant frame byte-for-byte.

Prints the declared record count, the length each record needs at the fixed
88-byte stride, and every record's item id and unit price, so a frame whose
header disagrees with its payload is visible directly.

Usage:
  python tools/dump_merchant_frame.py --session <uuid> --npc 5246
  python tools/dump_merchant_frame.py --source catalog --npc 5246
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import pathlib
import struct
import subprocess
import sys

CATALOGS = pathlib.Path(
    r"D:\Godswar-Reborn-main\artifacts\npc-port\shop-catalogs.json")
HEADER = 16
RECORD = 88


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def dump(frame: bytes, label: str) -> None:
    length = struct.unpack_from("<H", frame, 0)[0]
    declared = frame[10]
    body = frame[HEADER:length]
    print(f"\n--- {label}")
    print(f"    length={length} declared={declared} currency=0x{frame[9]:x} "
          f"category={frame[8]} fresh={frame[11]} balance="
          f"{struct.unpack_from('<i', frame, 12)[0]}")
    print(f"    body bytes={len(body)}  full records fit={len(body) // RECORD}  "
          f"remainder={len(body) % RECORD}  declared needs={declared * RECORD}")
    offset = 0
    index = 0
    while offset + 8 <= len(body):
        item = struct.unpack_from("<I", body, offset)[0]
        price = (struct.unpack_from("<I", body, offset + 68)[0]
                 if offset + 72 <= len(body) else None)
        short = " <short>" if offset + RECORD > len(body) else ""
        declared_mark = "" if index < declared else " <beyond-declared>"
        print(f"      [{index:>2}] off={offset:<5} id={item:<7} "
              f"price={price}{short}{declared_mark}")
        offset += RECORD
        index += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npc", type=int, required=True)
    parser.add_argument("--session")
    parser.add_argument("--source", choices=("capture", "catalog"),
                        default="capture")
    args = parser.parse_args()

    if args.source == "capture":
        if not args.session:
            print("--session is required for --source capture")
            return 1
        sql = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
               "WHERE opcode=10071 AND direction='S2C' AND capture_session_id="
               f"'{args.session}' ORDER BY id;")
        for line in psql(sql):
            frame = bytes.fromhex(line)
            if struct.unpack_from("<I", frame, 4)[0] == args.npc:
                dump(frame, f"capture len={len(frame)}")
        return 0

    catalogs = json.loads(CATALOGS.read_text(encoding="utf-8"))
    blob = gzip.decompress(base64.b64decode(
        catalogs[str(args.npc)]["gzipBase64"]))
    offset = 0
    while offset + HEADER <= len(blob):
        length = struct.unpack_from("<H", blob, offset)[0]
        dump(blob[offset:offset + length], f"catalog frame at {offset}")
        offset += length
    return 0


if __name__ == "__main__":
    sys.exit(main())
