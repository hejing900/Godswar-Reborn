"""Scan Origin.exe for call rel32 edges and answer "who calls X?".

The map file's addresses are stale, so this works purely from the executable:
decode every `E8 rel32` in .text, compute its target, and report the callers
of the requested addresses.

Usage:
  python tools/callers.py 0x6A09C0 0x5C8DF0
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

EXE = Path(r"D:\Godswar Origin\Origin.exe")
TEXT_START = 0x1000
TEXT_END = 0x51C000


def build_edges(data: bytes) -> dict[int, list[int]]:
    edges: dict[int, list[int]] = {}
    for offset in range(TEXT_START, TEXT_END - 5):
        if data[offset] != 0xE8:
            continue
        rel = struct.unpack_from("<i", data, offset + 1)[0]
        target = 0x400000 + offset + 5 + rel
        if not (0x400000 + TEXT_START <= target < 0x400000 + TEXT_END):
            continue
        edges.setdefault(target, []).append(0x400000 + offset)
    return edges


def main() -> int:
    data = EXE.read_bytes()
    edges = build_edges(data)
    print(f"# decoded {sum(len(v) for v in edges.values())} call edges, "
          f"{len(edges)} distinct targets")
    for token in sys.argv[1:]:
        target = int(token, 16)
        callers = edges.get(target, [])
        print(f"\n=== callers of 0x{target:08X}: {len(callers)}")
        for caller in callers:
            print(f"  0x{caller:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
