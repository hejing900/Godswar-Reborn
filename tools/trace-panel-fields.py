"""List every GameData field the attribute panel filler reads, in order.

The filler reloads the GameData pointer into a register and then reads fields
off it; tracking those registers (rather than pattern-matching offsets) yields
the complete ordered list, which is what the property rows align against. A
field read through a pointer that came out of GameData is reported as such.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EXE = r"D:\Godswar Origin\Origin.exe"
START = 0x005B54E0
END = 0x005B5B00
GAME_DATA = 0x01575EAC
WIRE_BASE = 0x254          # GameData = wire + 0x254 (proven by rep movsd)


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


def literal(image, image_base, sections, va):
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        if virtual_address <= va - image_base < virtual_address + raw_size:
            offset = raw_offset + (va - image_base - virtual_address)
            end = offset
            while 32 <= image[end] < 127 and end - offset < 60:
                end += 1
            return image[offset:end].decode("ascii", "replace")
    return "?"


REG_NAMES = ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True

    game_data_regs = set()
    pointer_regs = {}
    chunk = bytes(image[START - image_base:END - image_base])
    for insn in md.disasm(chunk, START):
        text = f"{insn.mnemonic} {insn.op_str}"
        operands = insn.operands

        # register = GameData (direct) or register += 0x25c
        if insn.mnemonic == "mov" and len(operands) == 2:
            dst, src = operands
            if (dst.type == CS_OP_REG and src.type == CS_OP_MEM
                    and src.mem.base == 0 and src.mem.index == 0
                    and src.mem.disp == GAME_DATA):
                game_data_regs.add(dst.reg)
                continue
            if dst.type == CS_OP_REG and src.type == CS_OP_REG:
                if src.reg in game_data_regs:
                    game_data_regs.add(dst.reg)
                elif dst.reg in game_data_regs:
                    game_data_regs.discard(dst.reg)
                if src.reg in pointer_regs:
                    pointer_regs[dst.reg] = pointer_regs[src.reg]
                elif dst.reg in pointer_regs:
                    del pointer_regs[dst.reg]
        elif insn.mnemonic == "add" and len(operands) == 2:
            dst, src = operands
            if (dst.type == CS_OP_REG and src.type == CS_OP_IMM
                    and dst.reg in game_data_regs):
                # only the +0x25c adjustment keeps it "the packet block"
                pass
        elif insn.mnemonic in ("movzx", "movsx", "mov", "cmp", "fld") and operands:
            src = operands[-1]
            if src.type == CS_OP_MEM:
                base = src.mem.base
                if base in game_data_regs:
                    wire = src.mem.disp - WIRE_BASE
                    size = insn.operands[0].size if operands[0].type == CS_OP_REG else 0
                    print(f"{insn.address:#010x}  {text:<40s} "
                          f"GameData+{src.mem.disp:#05x}  wire {wire}"
                          f"{'  [' + str(size * 8) + ' bit]' if size else ''}")
                elif base in pointer_regs:
                    print(f"{insn.address:#010x}  {text:<40s} "
                          f"通过指针 {REG_NAMES[base]} (来自 GameData+"
                          f"{pointer_regs[base]:#05x}) 读 +{src.mem.disp:#x}")

        if insn.mnemonic == "push" and operands and operands[0].type == CS_OP_IMM:
            value = operands[0].imm
            if 0x900000 <= value <= 0x9C0000:
                print(f"{insn.address:#010x}  {text:<40s} "
                      f'"{literal(image, image_base, sections, value)}"')

        # remember pointers taken out of GameData fields
        if insn.mnemonic == "mov" and len(operands) == 2:
            dst, src = operands
            if (dst.type == CS_OP_REG and src.type == CS_OP_MEM
                    and src.mem.base in game_data_regs):
                pointer_regs[dst.reg] = src.mem.disp
    return 0


if __name__ == "__main__":
    sys.exit(main())
