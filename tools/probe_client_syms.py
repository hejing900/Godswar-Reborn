"""Probe Origin.exe symbol alignment and dump selected functions.

Read-only analysis helper.
  python tools/probe_client_syms.py shift      # test +/- delta alignment on known symbols
  python tools/probe_client_syms.py dump <hexaddr> [count]
  python tools/probe_client_syms.py find <substr>
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disasm_petwork import CLIENT, MAP, load_pe_image, parse_map  # noqa: E402

PROLOGUES = (b"\x55\x8b\xec", b"\x6a\xff", b"\x83\xec", b"\x53\x56", b"\x56\x57", b"\x51\x53", b"\x55\x8b")


def shift_probe() -> None:
    image, base = load_pe_image(CLIENT)
    syms = parse_map(MAP)
    targets = [k for k in syms if any(s in k for s in ("CPetWorkUI", "onPetWorkReturn", "petWork@CPetUI", "CPetUI"))]
    targets.sort(key=lambda k: syms[k])
    for t in targets[:40]:
        rva = syms[t]
        row = []
        for delta in (-2, -1, 0, 1, 2):
            pro = image[rva + delta : rva + delta + 3]
            hit = "*" if pro in PROLOGUES or pro[:1] == b"\x55" else " "
            row.append(f"d{delta:+d}={pro.hex()}{hit}")
        print(f"0x{base + rva:08X} {t[:60]:62s} " + "  ".join(row))


def dump(addr: int, count: int, delta: int = 0) -> None:
    image, base = load_pe_image(CLIENT)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    syms = parse_map(MAP)
    by_rva = {v: k for k, v in syms.items()}
    start = addr + delta
    for insn in md.disasm(image[start - base : start - base + 0x800], start, count=count):
        note = ""
        if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == capstone.x86.X86_OP_IMM:
            tgt = insn.operands[0].imm
            for d in (0, -2, 2):
                nm = by_rva.get(tgt - base + d)
                if nm:
                    note = f"   ; {nm[:70]}"
                    break
            else:
                note = f"   ; sub_{tgt:X}"
        print(f"{insn.address:08X}  {insn.mnemonic:<8} {insn.op_str}{note}")


def find(substr: str) -> None:
    syms = parse_map(MAP)
    hits = sorted(((v, k) for k, v in syms.items() if substr in k))
    for rva, name in hits:
        print(f"0x{0x400000 + rva:08X} {name}")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shift"
    if cmd == "shift":
        shift_probe()
    elif cmd == "dump":
        addr = int(sys.argv[2], 16)
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        delta = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        dump(addr, count, delta)
    elif cmd == "find":
        find(sys.argv[2])
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
