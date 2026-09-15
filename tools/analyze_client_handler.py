"""Disassemble one of the installed client's opcode handlers with capstone.

The client ships its linker map, so call targets resolve to readable symbols and
the handler's own field offsets can be read off the instructions. That is how the
frame layouts are recovered from the binary instead of guessed.

Usage:
    python tools/analyze_client_handler.py 10082
    python tools/analyze_client_handler.py 10082 --length 0x400
"""

import re
import struct
import sys

import capstone

CLIENT = r"D:\Godswar Origin\Origin.exe"
MAP = r"D:\Godswar Origin\GodsWar.map"
IMAGE_BASE = 0x400000
LUT_VA = 0x4E3FD8
TABLE_VA = 0x4E3E2C
OPCODE_BASE = 10015


def load_image() -> tuple[bytes, list[tuple[int, int, int]]]:
    with open(CLIENT, "rb") as handle:
        image = handle.read()
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    sections = []
    for index in range(count):
        header = pe + 24 + optional + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", image, header + 8)
        sections.append((IMAGE_BASE + virtual_address, raw_offset,
                         max(virtual_size, raw_size)))
    return image, sections


def to_offset(sections, va: int) -> int:
    for base, raw, size in sections:
        if base <= va < base + size:
            return raw + (va - base)
    raise ValueError(f"0x{va:X} is outside every section")


def load_symbols() -> list[tuple[int, str]]:
    pattern = re.compile(r"^\s*0001:([0-9a-fA-F]{8})\s+(.*?)\s+([0-9a-fA-F]{8})\s")
    symbols: dict[int, str] = {}
    with open(MAP, "r", encoding="latin-1") as handle:
        for line in handle:
            match = pattern.match(line)
            if match:
                symbols.setdefault(int(match.group(3), 16), match.group(2).strip())
    return sorted(symbols.items())


def resolve(symbols, va: int) -> str:
    low, high = 0, len(symbols) - 1
    best = None
    while low <= high:
        middle = (low + high) // 2
        if symbols[middle][0] <= va:
            best = symbols[middle]
            low = middle + 1
        else:
            high = middle - 1
    if best is None:
        return f"0x{va:X}"
    delta = va - best[0]
    return best[1] if delta == 0 else f"{best[1]} +0x{delta:X}"


def handler_va(image: bytes, opcode: int) -> int:
    index = image[to_offset(load_image()[1], LUT_VA) + (opcode - OPCODE_BASE)]
    table = to_offset(load_image()[1], TABLE_VA)
    return struct.unpack_from("<I", image, table + index * 4)[0]


def main() -> int:
    args = list(sys.argv[1:])
    length = 0x400
    if "--length" in args:
        position = args.index("--length")
        length = int(args[position + 1], 0)
        del args[position:position + 2]
    image, sections = load_image()
    symbols = load_symbols()
    va = int(args[0], 0)
    if va < 0x10000:
        index = image[to_offset(sections, LUT_VA) + (va - OPCODE_BASE)]
        va = struct.unpack_from("<I", image, to_offset(sections, TABLE_VA) + index * 4)[0]
        print(f"opcode {args[0]} -> handler 0x{va:X}")
    code = image[to_offset(sections, va):to_offset(sections, va) + length]
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    print(f"== {resolve(symbols, va)} ==")
    for instruction in engine.disasm(code, va):
        note = ""
        if instruction.mnemonic == "call" and instruction.operands and \
                instruction.operands[0].type == capstone.x86.X86_OP_IMM:
            note = "  ; " + resolve(symbols, instruction.operands[0].imm)
        print(f"  0x{instruction.address:X}  {instruction.mnemonic:<8} "
              f"{instruction.op_str}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
