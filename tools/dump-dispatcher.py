"""Print the dispatcher head verbatim so its opcode base is unambiguous."""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
SPANS = [(0x004EA370, 0x004EA8A0), (0x004EE300, 0x004EE3E0)]


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
    md.skipdata = True
    for low, high in SPANS:
        print(f"=== {low:#x} .. {high:#x}")
        chunk = bytes(image[low - image_base:high - image_base])
        for insn in md.disasm(chunk, low):
            print(f"  {insn.address:#010x}  {insn.bytes.hex():<20s} "
                  f"{insn.mnemonic:8s} {insn.op_str}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
