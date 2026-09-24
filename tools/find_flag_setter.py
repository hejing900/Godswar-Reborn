"""Find where a one-byte flag at [obj+4] is written, to locate its setter.

Scans .text for `C6 40 04 imm8` (mov byte ptr [eax+4], imm8) style writes and
reports each site with the enclosing function start and a small disassembly
window, so the anti-addiction gate setter can be identified.

Usage: python tools/find_flag_setter.py [--offset 4]
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from disasm_petwork import CLIENT, load_pe_image  # noqa: E402

PROLOGUES = (b"\x55\x8b\xec", b"\x6a\xff", b"\x83\xec", b"\x53\x56", b"\x56\x57")


def find_function_start(data: bytes, offset: int, limit: int = 160) -> int | None:
    for back in range(0, limit):
        probe = data[offset - back : offset - back + 2]
        if probe in PROLOGUES:
            return offset - back
    return None


def main() -> int:
    offset = 4
    if "--offset" in sys.argv:
        offset = int(sys.argv[sys.argv.index("--offset") + 1], 0)
    data = Path(CLIENT).read_bytes()
    image, base = load_pe_image(CLIENT)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    prefixes = {
        "eax": bytes([0xC6, 0x40, offset]),
        "ecx": bytes([0xC6, 0x41, offset]),
        "edx": bytes([0xC6, 0x42, offset]),
        "ebx": bytes([0xC6, 0x43, offset]),
        "esi": bytes([0xC6, 0x46, offset]),
        "edi": bytes([0xC6, 0x47, offset]),
    }
    for register, pattern in prefixes.items():
        cursor = 0
        hits = []
        while True:
            cursor = data.find(pattern, cursor)
            if cursor < 0:
                break
            if 0x1000 <= cursor < 0x51C000:
                hits.append(cursor)
            cursor += 1
        if not hits:
            continue
        print(f"\n===== mov byte ptr [{register}+{offset}], imm8 : {len(hits)} site(s)")
        for hit in hits:
            imm = data[hit + 3] if len(data) > hit + 3 else 0
            start = find_function_start(data, hit)
            func = f"0x{base + start:08X}" if start is not None else "?"
            print(f"  site 0x{base + hit:08X}  imm=0x{imm:02X}  func~{func}")
            begin = (start if start is not None else hit) - 8
            for insn in md.disasm(
                image[begin : begin + 0x60], base + begin, count=10
            ):
                marker = "  <<<" if insn.address == base + hit else ""
                print(
                    f"      0x{insn.address:08X}  {insn.mnemonic:<7} "
                    f"{insn.op_str}{marker}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
