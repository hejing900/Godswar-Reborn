"""Find who installs the panel structure pointer (GameData+0x2A4).

The attribute panel prints 公会职位 from [pointer + 0x2B8], where the pointer is
read out of the game-data block our player-detail message fills. Nobody writes a
duty into that structure's field, so the question is who allocates the structure
and stores its pointer - that caller is the message which triggers the panel row.
Registers are tracked from the game-data base load so the address is resolved the
way the code computes it, not as a constant.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EXE = r"D:\Godswar Origin\Origin.exe"
GAME_DATA = 0x01575EAC
BLOCK_DELTA = 0x25C
SLOT_FROM_BASE = 0x2A4
SLOT_FROM_BLOCK = SLOT_FROM_BASE - BLOCK_DELTA       # 0x48
WINDOW = 0x8000


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
    text = next(s for s in sections if s[0] == ".text")
    _, text_rva, _, _, text_size = text
    start = image_base + text_rva
    code = bytes(image[text_rva:text_rva + text_size])

    hits = []
    for window in range(0, text_size, WINDOW):
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        md.skipdata = True
        base_regs = set()
        block_regs = set()
        for insn in md.disasm(code[window:window + WINDOW], start + window):
            if insn.id == 0:
                continue
            try:
                operands = insn.operands
            except Exception:
                continue
            if not operands:
                continue
            mnemonic = insn.mnemonic
            dst, src = operands[0], operands[-1]

            if mnemonic == "mov" and dst.type == CS_OP_REG:
                if (src.type == CS_OP_MEM and src.mem.base == 0
                        and src.mem.index == 0 and src.mem.disp == GAME_DATA):
                    base_regs = {dst.reg}
                    block_regs = set()
                    continue
                if dst.reg in base_regs and src.type == CS_OP_REG:
                    if src.reg in base_regs:
                        pass
                    else:
                        base_regs.discard(dst.reg)
                if dst.reg in block_regs and src.type != CS_OP_REG:
                    block_regs.discard(dst.reg)
            if mnemonic == "add" and dst.type == CS_OP_REG and src.type == CS_OP_IMM:
                if dst.reg in base_regs and src.imm == BLOCK_DELTA:
                    base_regs.discard(dst.reg)
                    block_regs.add(dst.reg)
                    continue

            if mnemonic in ("mov", "movzx", "movsx", "and", "or", "add", "sub") \
                    and dst.type == CS_OP_MEM and dst.mem.index == 0:
                if dst.mem.base in base_regs and dst.mem.disp == SLOT_FROM_BASE:
                    hits.append((insn.address, f"{mnemonic} {insn.op_str}",
                                 "GameData+0x2A4"))
                elif dst.mem.base in block_regs and dst.mem.disp == SLOT_FROM_BLOCK:
                    hits.append((insn.address, f"{mnemonic} {insn.op_str}",
                                 "block+0x48"))

    print(f"{len(hits)} writes to the panel-structure pointer slot")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.skipdata = True
    for address, text_form, note in hits:
        print(f"\n--- {note}  {address:#x}  {text_form}")
        low = address - 0x40
        for insn in md.disasm(
                bytes(image[low - image_base:address + 8 - image_base]), low):
            marker = "  <== WRITE" if insn.address == address else ""
            print(f"    {insn.address:#010x}  {insn.mnemonic:8s} "
                  f"{insn.op_str}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
