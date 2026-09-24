"""Search Origin.exe for small-integer constants (candidate wire opcodes).

Read-only analysis helper.  Prints every file offset where the little-endian
encoding of the requested value appears, plus the VA (base 0x400000).

Usage:
  python tools/scan_opcodes.py 10250 10251 10252
  python tools/scan_opcodes.py --str 0x9510d0
"""
from __future__ import annotations

import sys
from pathlib import Path

EXE = Path(r"D:\Godswar Origin\Origin.exe")
BASE = 0x400000


def read_cstr(data: bytes, va: int) -> str:
    off = va - BASE
    end = data.find(b"\x00", off)
    return data[off:end].decode("latin1", "replace")


def main() -> int:
    data = EXE.read_bytes()
    args = sys.argv[1:]
    if args and args[0] == "--str":
        for token in args[1:]:
            print(hex(int(token, 16)), "->", repr(read_cstr(data, int(token, 16))))
        return 0
    for token in args:
        value = int(token, 0)
        for width in (2, 4):
            needle = value.to_bytes(width, "little")
            hits: list[int] = []
            cursor = 0
            while True:
                found = data.find(needle, cursor)
                if found < 0:
                    break
                cursor = found + 1
                hits.append(found)
                if len(hits) > 400:
                    break
            text_hits = [h for h in hits if 0x1000 <= h < 0x51C000]
            if text_hits:
                print(f"value {value} width {width}: {len(text_hits)} code hit(s) "
                      f"-> {[hex(h) for h in text_hits[:40]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
