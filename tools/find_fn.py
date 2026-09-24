"""Locate a function by its map-file byte signature, then disassemble it.

The shipped Origin.exe is patched, so GodsWar.map addresses are stale by a few
bytes. We therefore take the map address, extract the bytes the map implies,
search the image for that exact sequence, and derive the real address.

Usage:
  python tools/find_fn.py <map-symbol-substring> [count]
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disasm_petwork import CLIENT, MAP, load_pe_image, parse_map  # noqa: E402


def disasm_range(image: bytes, syms: dict[str, int], addr: int, count: int, label: str) -> None:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    by_rva = {}
    for name, rva in syms.items():
        by_rva.setdefault(rva, name)
    base = 0x400000
    print(f"\n===== {label} @ 0x{addr:08X}")
    off = addr - base
    for insn in md.disasm(image[off : off + 0x600], addr, count=count):
        note = ""
        if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == capstone.x86.X86_OP_IMM:
            tgt = insn.operands[0].imm
            nm = by_rva.get(tgt - base)
            note = f"   ; {nm[:60]}" if nm else ""
        print(f"{insn.address:08X}  {insn.mnemonic:<8} {insn.op_str}{note}")


def main() -> int:
    needle = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    image, base = load_pe_image(CLIENT)
    syms = parse_map(MAP)
    matches = sorted((rva, n) for n, rva in syms.items() if needle in n)
    if not matches:
        print("no symbol matches")
        return 1
    for rva, name in matches:
        sig = image[rva : rva + 24]
        print(f"symbol {name[:80]}")
        print(f"  map addr 0x{base + rva:08X} expected bytes {sig.hex(' ')}")
        found = image.find(sig)
        if found < 0:
            print("  signature not found in image")
            continue
        print(f"  signature found at 0x{base + found:08X} (delta {found - rva:+d})")
        disasm_range(image, syms, base + found, count, name[:50])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
