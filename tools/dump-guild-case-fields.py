"""Dump what each guild message case reads off the wire.

The client's receive dispatcher (0x4ea3d0) picks a case per opcode through the
byte table at 0x4ee900 and the jump table at 0x4ee82c. Every case body receives
the decoded packet struct in edi, whose layout is measured: opcode at +6, payload
at +8 - so `[edi+4]` is the "packet base" the case hands to its handler, and a
field at body+X shows up as `[edi+8+X]` here or as `arg+8+X` inside a callee.

Usage: python tools/dump-guild-case-fields.py [opcode ...]
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
DISPATCH_BASE_OPCODE = 10001
SLOT_TABLE = 0x4EE900
JUMP_TABLE = 0x4EE82C

DEFAULT_OPCODES = [
    10139, 10140, 10141, 10142, 10144, 10145, 10146,
    10147, 10148, 10150, 10151, 10152, 10154, 10157, 10162,
]


def load_image(path):
    data = open(path, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    base = struct.unpack_from("<I", data, optional + 28)[0]
    sections = []
    table = optional + optional_size
    for index in range(section_count):
        entry = table + (index * 40)
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, entry + 8
        )
        sections.append((virtual_address, virtual_size, raw_offset, raw_size))
    image = bytearray(max(va + max(vs, rs) for va, vs, _, rs in sections))
    for virtual_address, _, raw_offset, raw_size in sections:
        image[virtual_address:virtual_address + raw_size] = data[
            raw_offset:raw_offset + raw_size
        ]
    return image, base


def main():
    wanted = [int(arg) for arg in sys.argv[1:]] or DEFAULT_OPCODES
    image, base = load_image(EXE)
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.skipdata = True

    cases = {}
    for opcode in wanted:
        slot = image[SLOT_TABLE + (opcode - DISPATCH_BASE_OPCODE) - base]
        target = struct.unpack_from(
            "<I", image, JUMP_TABLE + (slot * 4) - base
        )[0]
        cases[opcode] = target

    ordered = sorted(cases.items(), key=lambda item: item[1])
    for index, (opcode, start) in enumerate(ordered):
        end = (
            ordered[index + 1][1]
            if index + 1 < len(ordered)
            else start + 0x120
        )
        end = min(end, start + 0x120)
        print(f"=== {opcode} (0x{opcode:04x})  case 0x{start:08x}")
        for ins in decoder.disasm(
            bytes(image[start - base:end - base]), start
        ):
            text = f"{ins.mnemonic} {ins.op_str}"
            interesting = (
                "[" in text
                or ins.mnemonic == "call"
                or ins.mnemonic.startswith("j")
            )
            if interesting:
                note = ""
                if ins.mnemonic == "call":
                    note = "   <- handler"
                print(f"  {ins.address:#010x}  {text}{note}")
        print()


if __name__ == "__main__":
    main()
