"""List the attribute panel filler's field reads in order.

The panel builds its rows from the GameData block our player-detail message
fills, so the order in which the filler reads that block (and the format/key it
pairs each read with) is what identifies the 公会职位 row's offset. Only the
high-signal instructions are printed: GameData field reads, literal pushes and
calls into the row objects.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
START = 0x005B54E0
END = 0x005B5A00


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
            while 32 <= image[end] < 127 and end - offset < 80:
                end += 1
            return image[offset:end].decode("ascii", "replace")
    return "?"


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.skipdata = True

    chunk = bytes(image[START - image_base:END - image_base])
    for insn in md.disasm(chunk, START):
        text = f"{insn.mnemonic} {insn.op_str}"
        keep = None
        if "+ 0x2" in text and "ptr [" in text:
            keep = "GameData 字段"
        elif insn.mnemonic == "push" and insn.op_str.startswith("0x9"):
            keep = f'字面量 "{literal(image, image_base, sections, int(insn.op_str, 16))}"'
        elif "0x95b" in insn.op_str and insn.mnemonic == "push":
            keep = "键"
        elif insn.mnemonic == "call" and insn.op_str.startswith("0x5b4"):
            keep = "面板/行函数"
        if keep:
            print(f"{insn.address:#010x}  {text:<44s} {keep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
