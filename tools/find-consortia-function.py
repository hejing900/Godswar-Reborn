"""Find the function that owns the consortia case bodies and read its switch.

The case bodies share one epilogue, so they belong to a single large function.
This walks backwards from a case body to the function's prologue, disassembles
the whole function, and prints every opcode-shaped immediate plus every indexed
jump so the dispatch of the message type can be read directly.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_MEM, CS_OP_IMM

EXE = r"D:\Godswar Origin\Origin.exe"
ANCHOR = 0x4ECDA3          # push "MSG_CONSORTIA_CREATE_RESPONSE"
SEARCH_BACK = 0x8000       # how far back the function head may sit
FUNCTION_SPAN = 0x9000


def load_pe(path):
    with open(path, "rb") as handle:
        data = handle.read()
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    optional = pe_offset + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    image_base = (struct.unpack_from("<I", data, optional + 28)[0]
                  if magic == 0x10B
                  else struct.unpack_from("<Q", data, optional + 24)[0])
    sections = []
    table = optional + optional_size
    for index in range(section_count):
        entry = table + (index * 40)
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii", "replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, entry + 8)
        sections.append((name, virtual_address, virtual_size, raw_offset, raw_size))
    return data, image_base, sections


def build_image(data, image_base, sections):
    size = max(virtual_address + max(virtual_size, raw_size)
               for _, virtual_address, virtual_size, _, raw_size in sections)
    image = bytearray(size)
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        chunk = data[raw_offset:raw_offset + raw_size]
        image[virtual_address:virtual_address + len(chunk)] = chunk
    return image


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)

    # Walk back to the padding that ends the previous function.
    anchor_offset = ANCHOR - image_base
    head = None
    for offset in range(anchor_offset, anchor_offset - SEARCH_BACK, -1):
        if (image[offset] == 0xCC and image[offset + 1] == 0xCC
                and image[offset + 2] == 0xCC and image[offset + 3] == 0xCC
                and image[offset + 4] != 0xCC):
            head = image_base + offset + 1
            break
    print(f"anchor {ANCHOR:#x}, function head candidate "
          f"{head if head is None else hex(head)}")

    start = ANCHOR - 0x400 if head is None else head
    start = max(image_base + 0x1000, start)
    chunk = bytes(image[start - image_base:start - image_base + FUNCTION_SPAN])

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    print(f"disassembling from {start:#x}\n")
    print("--- opcode-shaped immediates (0x2000..0x3200) ---")
    for insn in md.disasm(chunk, start):
        if insn.mnemonic in ("cmp", "sub", "mov", "movzx", "add", "lea"):
            for operand in insn.operands:
                if operand.type == CS_OP_IMM:
                    value = operand.imm
                    if 0x2000 <= value <= 0x3200:
                        print(f"  {insn.address:#010x}  "
                              f"{insn.mnemonic:8s} {insn.op_str}")
        if insn.mnemonic == "jmp" and insn.operands:
            operand = insn.operands[0]
            if operand.type == CS_OP_MEM and operand.mem.index:
                print(f"  TABLE {insn.address:#010x}  {insn.mnemonic} "
                      f"{insn.op_str}")

    print("\n--- indexed indirect jumps in this span ---")
    for insn in md.disasm(chunk, start):
        if insn.mnemonic in ("jmp", "call") and insn.operands:
            operand = insn.operands[0]
            if operand.type == CS_OP_MEM and operand.mem.index:
                print(f"  {insn.address:#010x}  {insn.mnemonic} {insn.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
