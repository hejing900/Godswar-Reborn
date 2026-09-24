"""Read the click answer for one npc from any session (helper for parity checks).

Usage: python tools/show_click_answer.py --npc 5459 [--session <uuid>]
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import sys


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npc", type=int, required=True)
    parser.add_argument("--session")
    args = parser.parse_args()

    where = "opcode=10067 AND direction='S2C'"
    if args.session:
        where += f" AND capture_session_id='{args.session}'"
    sql = (f"SELECT id, encode(clear_bytes,'hex') FROM packet_transactions "
           f"WHERE {where} ORDER BY id;")

    found = 0
    for line in psql(sql):
        row_id, hexed = line.split("|", 1)
        data = bytes.fromhex(hexed)
        if len(data) < 20:
            continue
        npc_id, flags, packed = struct.unpack_from("<III", data, 4)
        if npc_id != args.npc:
            continue
        found += 1
        tail = data[16:]
        end = tail.index(b"\0") if b"\0" in tail else len(tail)
        print(f"row {row_id}: npc={npc_id} flags=0x{flags:x} "
              f"packed=0x{packed:x} key={tail[:end].decode('ascii', 'replace')!r}")
        print(f"    {hexed}")
    if not found:
        print(f"npc {args.npc}: no 10067 S2C frame")
    return 0


if __name__ == "__main__":
    sys.exit(main())
