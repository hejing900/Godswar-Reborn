"""Find who writes the byte the attribute panel prints as 公会职位.

The panel reads [structure + 0x2B8]; this lists every instruction that writes
that offset through a register base (stack-relative hits are filtered out) and
shows the instructions just before it, so the value's origin is visible.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_MEM

EXE = r"D:\Godswar Origin\Origin.exe"
TARGET = 0x2B8


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
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    text = next(s for s in sections if s[0] == ".text")
    _, text_rva, _, _, text_size = text
    start = image_base + text_rva
    code = bytes(image[text_rva:text_rva + text_size])

    writes = []
    # Detail mode over five megabytes exhausts capstone, so walk the section in
    # windows and rebuild the decoder for each one.
    window = 0x8000
    for base in range(0, text_size, window):
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        md.skipdata = True
        chunk = code[base:base + window]
        for insn in md.disasm(chunk, start + base):
            if insn.id == 0:
                continue
            try:
                operands = insn.operands
            except Exception:
                continue
            if not operands:
                continue
            dst = operands[0]
            if dst.type != CS_OP_MEM or dst.mem.disp != TARGET:
                continue
            if dst.mem.base == 4:      # esp -> stack
                continue
            writes.append(insn.address)

    print(f"{len(writes)} register-based writes to +{TARGET:#x}")
    for address in writes:
        low = address - 0x30
        print(f"\n--- write at {address:#x}")
        chunk = bytes(image[low - image_base:address + 8 - image_base])
        for insn in md.disasm(chunk, low):
            marker = "  <== WRITE" if insn.address == address else ""
            print(f"    {insn.address:#010x}  {insn.mnemonic:8s} "
                  f"{insn.op_str}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
