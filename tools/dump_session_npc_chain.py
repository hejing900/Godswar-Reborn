"""Dump every NPC-relevant frame of one capture session, grouped per NPC.

Reads packet_transactions (the live capture the proxy is writing) and walks the
protocol framing inside each chunk, so a click chain can be read off directly:

    C2S 10067 click -> S2C 10067 open (flags + packed function list + script)
    -> C2S 10068 page requests -> C2S 10069 picks -> S2C 10070 answers
    -> S2C 10071 shop catalogues

Usage:
  python tools/dump_session_npc_chain.py --session <uuid> [--from "2026-09-28 01:52:00"]
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import sys

WATCH = {10067, 10068, 10069, 10070, 10071}

LABEL = {10067: "OPEN", 10068: "PAGE", 10069: "ACT", 10070: "MENU",
         10071: "SHOP"}


def psql(sql: str) -> list[str]:
    done = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        sys.stderr.write(done.stderr or "")
        raise SystemExit(1)
    return [l for l in (done.stdout or "").splitlines() if l.strip()]


def unpack_functions(packed: int) -> list[int]:
    out = []
    while packed:
        packed, digit = divmod(packed, 1000)
        out.append(digit)
    return out


def describe(op: int, direction: str, frame: bytes) -> str:
    if op == 10067:
        npc, = struct.unpack_from("<I", frame, 4)
        flags, = struct.unpack_from("<I", frame, 8)
        packed, = struct.unpack_from("<I", frame, 12)
        raw = frame[16:]
        zero = raw.find(b"\x00")
        script = raw[:zero if zero >= 0 else len(raw)].decode("ascii", "replace")
        return (f"npcs={npc} flags=0x{flags:X} "
                f"fns={unpack_functions(packed)} script={script!r}")
    if op == 10068:
        npc, = struct.unpack_from("<I", frame, 4)
        return f"npc={npc}"
    if op == 10069:
        npc, = struct.unpack_from("<I", frame, 4)
        fn, = struct.unpack_from("<I", frame, 8)
        fn2, = struct.unpack_from("<I", frame, 12)
        pick, = struct.unpack_from("<i", frame, 16)
        sub, = struct.unpack_from("<i", frame, 20)
        args = [struct.unpack_from("<i", frame, o)[0]
                for o in range(24, min(len(frame), 56), 4)]
        return (f"npc={npc} fn={fn} fn2={fn2} pick={pick} sub={sub} "
                f"args={args}")
    if op == 10070:
        npc, = struct.unpack_from("<I", frame, 4)
        dialog, = struct.unpack_from("<I", frame, 8)
        vals = [struct.unpack_from("<i", frame, o)[0]
                for o in range(12, len(frame) - 3, 4)]
        return f"npc={npc} dialog={dialog} values={vals}"
    if op == 10071:
        npc, = struct.unpack_from("<I", frame, 4)
        return (f"npc={npc} cat={frame[8]} cur=0x{frame[9]:02X} "
                f"count={frame[10]} fresh={frame[11]} "
                f"balance={struct.unpack_from('<i', frame, 12)[0]} "
                f"len={len(frame)}")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--from", dest="start", default=None,
                        help="local time, e.g. '2026-09-28 01:52:00'")
    parser.add_argument("--to", dest="end", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    where = (f"capture_session_id='{args.session}' "
             f"AND opcode IN (10067,10068,10069,10070,10071)")
    if args.start:
        where += (f" AND captured_at + interval '8 hours' >= "
                  f"timestamp '{args.start}'")
    if args.end:
        where += (f" AND captured_at + interval '8 hours' < "
                  f"timestamp '{args.end}'")

    rows = psql("SELECT id, to_char(captured_at + interval '8 hours', "
                "'HH24:MI:SS.MS'), direction, encode(clear_bytes,'hex') "
                f"FROM packet_transactions WHERE {where} ORDER BY id;")

    lines: list[str] = []
    for row in rows:
        row_id, clock, direction, blob = row.split("|", 3)
        data = bytes.fromhex(blob)
        offset = 0
        while offset + 4 <= len(data):
            length, op = struct.unpack_from("<HH", data, offset)
            if length < 4 or offset + length > len(data):
                break
            frame = data[offset:offset + length]
            if op in WATCH:
                lines.append(f"{row_id:>7} {clock} {direction:<4} "
                             f"{LABEL[op]:<5} {describe(op, direction, frame)}")
            offset += length

    text = "\n".join(lines)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"\nwrote {args.out} ({len(lines)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
