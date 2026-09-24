"""Recover the opcodes that dispatch the consortia messages.

Plan: disassemble .text with capstone, find every indirect jump whose memory
operand indexes a table, read those tables, and report which table entry lands
on a consortia case body. The instructions right before the indirect jump give
the table index base, which turns an entry index into the wire opcode.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_MEM, CS_OP_IMM

EXE = r"D:\Godswar Origin\Origin.exe"

# Case bodies: (label, address of the `push "MSG_..."` inside the case).
CASES = [
    ("MSG_CONSORTIA_CREATE_RESPONSE", 0x4ECDA3),
    ("MSG_CONSORTIA_INVITE", 0x4ED2A4),
    ("MSG_CONSORTIA_EXIT", 0x4ED4DF),
    ("MSG_CONSORTIA_TEXT", 0x4ED670),
    ("MSG_CONSORTIA_DISMISS", 0x4ED69D),
    ("MSG_CONSORTIA_DUTY", 0x4ED78F),
    ("MSG_CONSORTIA_MEMBER_DEL", 0x4ED882),
    ("MSG_CONSORTIA_RESPONSE", 0x4EDA24),
    ("MSG_CONSORTIA_BASE_INFO", 0x4EDA3B),
    ("MSG_CONSORTIA_MEMBER_LIST", 0x4EDB5D),
    ("MSG_CONSORTIA_MEMBER_ONE", 0x4EDC77),
    ("MSG_CONSORTIA_NOTE", 0x4EDF46),
    ("MSG_ALTAR_INFO", 0x4EDF0C),
    ("MSG_CONSORTIA_ELEMENT_LIST", 0x4EDFC6),
    ("MSG_CONSORTIA_MEMBER_ADD_MSG", 0x4DF151),
]

REGION_LOW = 0x4EC000
REGION_HIGH = 0x4E0000 + 0x4000


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
    """Materialise the loaded image so VAs can be read directly."""
    size = max(virtual_address + max(virtual_size, raw_size)
               for _, virtual_address, virtual_size, _, raw_size in sections)
    image = bytearray(size)
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        chunk = data[raw_offset:raw_offset + raw_size]
        image[virtual_address:virtual_address + len(chunk)] = chunk
    return image


def read_dword(image, va):
    offset = va
    if offset + 4 > len(image):
        return None
    return struct.unpack_from("<I", image, offset)[0]


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)
    text = next(s for s in sections if s[0] == ".text")
    _, text_rva, _, text_off, text_size = text
    text_start = image_base + text_rva
    code = bytes(image[text_rva:text_rva + text_size])

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    tables = {}
    instruction_count = 0
    for insn in md.disasm(code, text_start):
        instruction_count += 1
        mnemonic = insn.mnemonic
        if mnemonic not in ("jmp", "call"):
            continue
        if not insn.operands:
            continue
        operand = insn.operands[0]
        if operand.type != CS_OP_MEM:
            continue
        mem = operand.mem
        # Jump tables are indexed: [reg*scale + disp] or [reg + reg*scale + disp].
        if mem.index == 0:
            continue
        table_va = mem.disp
        if table_va < image_base:
            continue
        scale = mem.scale or 1
        entries = []
        for slot in range(0, 64):
            entry = read_dword(image, table_va - image_base + (slot * 4))
            if entry is None or entry < image_base:
                break
            entries.append(entry)
        if not entries:
            continue
        if any(REGION_LOW <= entry <= REGION_HIGH for entry in entries):
            tables[insn.address] = (table_va, entries, insn)

    print(f"{instruction_count} instructions, "
          f"{len(tables)} indexed jump tables reaching the consortia region\n")
    for address in sorted(tables):
        table_va, entries, insn = tables[address]
        print(f"=== indirect jump at {address:#x}: "
              f"{insn.mnemonic} {insn.op_str}")
        print(f"    table base {table_va:#x} ({len(entries)} entries read)")
        for index, entry in enumerate(entries):
            label = next((name for name, target in CASES
                          if target - 0x80 <= entry <= target + 0x20), None)
            marker = f"   <-- {label}" if label else ""
            if label or index < 4:
                print(f"      [{index:3d}] {entry:#010x}{marker}")
        # The base constant is set up before the jump.
        back = max(text_start, address - 0x60)
        chunk = bytes(image[back - image_base:address + insn.size - image_base])
        print("    preceding instructions:")
        for pre in md.disasm(chunk, back):
            if pre.address >= address:
                break
            print(f"      {pre.address:#010x}  "
                  f"{pre.mnemonic:8s} {pre.op_str}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
