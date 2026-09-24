"""Disassemble client pet-work code paths from Origin.exe using the MAP symbols.

Read-only analysis helper. Requires: pip install capstone (already present).
Usage:
  python tools/disasm_petwork.py <symbol-substring> [count]
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import capstone

CLIENT = Path(r"D:\Godswar Origin\Origin.exe")
MAP = Path(r"D:\Godswar Origin\GodsWar.map")


def load_pe_image(path: Path) -> tuple[bytes, int]:
    """Return (image bytes laid out at RVA 0, image base)."""
    data = path.read_bytes()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew : e_lfanew + 4] == b"PE\0\0"
    coff = e_lfanew + 4
    num_sections = struct.unpack_from("<H", data, coff + 2)[0]
    size_opt = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    image_base = struct.unpack_from("<I", data, opt + 28)[0] if magic == 0x10B else struct.unpack_from("<Q", data, opt + 24)[0]
    sections = []
    sec = opt + size_opt
    for i in range(num_sections):
        off = sec + i * 40
        name = data[off : off + 8].rstrip(b"\0").decode("latin1")
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append((name, va, vsize, raw_ptr, raw_size))
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
    image = bytearray(size_of_image + 0x1000)
    for name, va, vsize, raw_ptr, raw_size in sections:
        n = min(vsize if vsize else raw_size, raw_size)
        if raw_ptr and n:
            image[va : va + n] = data[raw_ptr : raw_ptr + n]
    return bytes(image), image_base


def parse_map(path: Path) -> dict[str, int]:
    """Symbol name -> RVA (map addresses are absolute VA, image base 0x400000)."""
    syms: dict[str, int] = {}
    base = 0x400000
    for enc in ("latin1", "utf-8", "gb2312"):
        try:
            text = path.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if "PetWork" in text:
            break
    else:
        raise SystemExit("map decode failed")
    for line in text.splitlines():
        parts = line.split()
        # " 0001:0001d3f0  ?name@@... 0041e3f0 f i Module.obj"
        if len(parts) < 4 or ":" not in parts[0]:
            continue
        name = parts[1]
        va = None
        for token in parts[2:]:
            if len(token) == 8:
                try:
                    va = int(token, 16)
                except ValueError:
                    continue
                break
        if va is None or va < base:
            continue
        syms.setdefault(name, va - base)
    return syms


def main() -> int:
    needle = sys.argv[1] if len(sys.argv) > 1 else "CPetWorkUI"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    image, image_base = load_pe_image(CLIENT)
    syms = parse_map(MAP)
    print(f"# image_base=0x{image_base:X} symbols={len(syms)}")
    hits = [(n, r) for n, r in syms.items() if needle in n]
    hits.sort(key=lambda kv: kv[1])
    print(f"# {len(hits)} symbols matching {needle!r}")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    for name, rva in hits:
        # skip compiler internals unless the needle is explicit
        if needle == "CPetWorkUI" and not name.startswith("?"):
            pass
        print(f"\n===== 0x{image_base + rva:08X} {name}")
        code = image[rva : rva + 0x400]
        emitted = 0
        for insn in md.disasm(code, image_base + rva):
            text = f"  {insn.address:08X}  {insn.mnemonic:<7} {insn.op_str}"
            print(text)
            emitted += 1
            if emitted >= count:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
