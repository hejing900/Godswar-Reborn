"""Trace the client's outgoing-message builder to recover a C2S opcode.

`CPetWorkUI::doWork` (0x5C8DF0) validates, builds a query string, calls
sub_5C9240, then writes 0x26 into a command singleton and calls sub_596DE0.
This script walks that path and dumps the opcode write sites.

Usage: python tools/trace_c2s_opcode.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disasm_petwork import CLIENT, load_pe_image  # noqa: E402

BASE = 0x400000


def disasm(image: bytes, addr: int, count: int, label: str) -> None:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    print(f"\n===== {label} @ 0x{addr:08X}")
    off = addr - BASE
    for insn in md.disasm(image[off : off + 0x400], addr, count=count):
        # flag immediate writes that look like opcodes
        note = ""
        if insn.mnemonic in ("mov", "push") and "0x28" in insn.op_str:
            note = "   <== 0x28xx range"
        print(f"{insn.address:08X}  {insn.mnemonic:<8} {insn.op_str}{note}")


def main() -> int:
    image, _ = load_pe_image(CLIENT)
    for addr, n, label in (
        (0x5C9240, 70, "sub_5C9240 (query builder called by doWork)"),
        (0x596DE0, 60, "sub_596DE0 (command dispatch tail)"),
        (0x5968C0, 60, "sub_5968C0 (candidate opcode write site)"),
        (0x5C93C0, 80, "S2C 10291 handler 0x5C93C0"),
    ):
        disasm(image, addr, n, label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
