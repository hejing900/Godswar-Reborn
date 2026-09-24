"""Decode the reference server's click answers into a per-NPC function map.

Opcode 10067 S2C is the answer to a client click. Layout, verified against the
2026-09-24 late session:

  +0  u16 length (48)
  +2  u16 opcode (10067)
  +4  u32 runtime npc id      (the id the same capture's 10020/10071 used)
  +8  u32 flags
  +12 u32 function numbers, packed base-1000 (each digit is one function id,
          least significant first; 0x00001f4e -> 6, 2, 2 ... see unpack())
  +16 ASCII zero-terminated npc script key ("Athens_050")

The function number is what the client echoes back as its dialog index, so this
table is the authoritative binding between an npc and the service it offers -
including which npcs are merchants.

Usage: python tools/decode_click_answers.py --session <uuid> [--json FILE]
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
import subprocess
import sys

PACK_BASE = 1000


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def unpack(packed: int) -> list[int]:
    """Unpack the base-1000 function list, dropping the zero terminator."""
    if packed == 0:
        return []
    digits = []
    value = packed
    while value:
        digits.append(value % PACK_BASE)
        value //= PACK_BASE
    return [d for d in digits if d != 0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--json")
    args = parser.parse_args()

    sql = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
           "WHERE opcode=10067 AND direction='S2C' "
           f"AND capture_session_id='{args.session}' ORDER BY id;")

    by_npc: dict[int, dict] = {}
    for line in psql(sql):
        data = bytes.fromhex(line)
        if len(data) < 20:
            continue
        npc_id, flags, packed = struct.unpack_from("<III", data, 4)
        tail = data[16:]
        end = tail.index(b"\0") if b"\0" in tail else len(tail)
        key = tail[:end].decode("ascii", "replace")
        entry = by_npc.setdefault(npc_id, {
            "npcKey": key, "flags": set(), "packed": set(), "functions": set(),
            "clicks": 0,
        })
        entry["flags"].add(flags)
        entry["packed"].add(packed)
        entry["functions"].update(unpack(packed))
        entry["clicks"] += 1

    print(f"{'npc id':>7}  {'script key':<24} {'clicks':>6}  {'packed':>12}  functions")
    for npc_id in sorted(by_npc):
        entry = by_npc[npc_id]
        packed = sorted(entry["packed"])
        packed_text = ",".join(f"0x{p:x}" for p in packed)
        print(f"{npc_id:>7}  {entry['npcKey']:<24} {entry['clicks']:>6}  "
              f"{packed_text:>12}  {sorted(entry['functions'])}")

    print(f"\nnpcs clicked: {len(by_npc)}")
    all_functions = collections.Counter()
    for entry in by_npc.values():
        for function in entry["functions"]:
            all_functions[function] += 1
    print(f"distinct function numbers: {sorted(all_functions)}")

    if args.json:
        payload = {str(k): {"npcKey": v["npcKey"],
                            "functions": sorted(v["functions"]),
                            "flags": sorted(v["flags"]),
                            "packed": sorted(v["packed"]),
                            "clicks": v["clicks"]}
                   for k, v in by_npc.items()}
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
