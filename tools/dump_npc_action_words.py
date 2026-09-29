"""Dump every word of the C2S 10069 action frames for one NPC, with the reply.

The client's action packet is a fixed 92-byte frame whose +16 word is the number
the player clicked and whose following words carry the second-level number a
form or confirm page submits. Printing all of them - and the 10070 the server
answered with - shows which word the reference's dispatch reads.

Usage:
  python tools/dump_npc_action_words.py --session <uuid> --npc 5057
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WATCH = (10069, 10070)


def psql(sql: str) -> list[str]:
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        sys.stderr.write(done.stderr or "")
        raise SystemExit(1)
    return [l for l in (done.stdout or "").splitlines() if l.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--npc", type=int, required=True)
    args = parser.parse_args()

    rows = psql(
        "SELECT id, to_char(captured_at + interval '8 hours', "
        "'HH24:MI:SS.MS'), direction, opcode, encode(clear_bytes,'hex') "
        "FROM packet_transactions "
        f"WHERE capture_session_id='{args.session}' "
        "AND opcode IN (10069, 10070) ORDER BY id;")

    last_action_npc = None
    for row in rows:
        row_id, clock, direction, opcode, blob = row.split("|", 4)
        data = bytes.fromhex(blob)
        offset = 0
        while offset + 4 <= len(data):
            length, op = struct.unpack_from("<HH", data, offset)
            if length < 4 or offset + length > len(data):
                break
            frame = data[offset:offset + length]
            offset += length
            if op not in WATCH:
                continue
            npc, = struct.unpack_from("<I", frame, 4)
            if npc != args.npc:
                continue
            if op == 10069:
                words = [struct.unpack_from("<i", frame, o)[0]
                         for o in range(8, len(frame) - 3, 4)]
                print(f"{row_id:>7} {clock} C2S 10069 words={words}")
            else:
                dialog, = struct.unpack_from("<I", frame, 8)
                values = [struct.unpack_from("<i", frame, o)[0]
                          for o in range(12, len(frame) - 3, 4)]
                print(f"{row_id:>7} {clock} S2C 10070 dialog={dialog} "
                      f"values={values}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
