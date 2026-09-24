"""Find what fills the character panel's 公会职位 (Positionpro) field.

Message.dat names the panel's guild-position label `Positionpro`; the client
looks that key up at runtime, so the literal lives in the image next to the code
that reads the value it prints.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
KEYS = ("Positionpro", "Jobpro", "YourPosition")


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

    for key in KEYS:
        literal = data.find(key.encode("ascii") + b"\0")
        if literal < 0:
            print(f"=== {key}: no literal")
            continue
        literal_va = None
        for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
            if raw_offset <= literal < raw_offset + raw_size:
                literal_va = image_base + virtual_address + (literal - raw_offset)
                break
        print(f"=== {key}: literal {literal_va:#x}")
        cursor = 0
        needle = b"\x68" + struct.pack("<I", literal_va)
        while True:
            site = data.find(needle, cursor)
            if site < 0:
                break
            cursor = site + 1
            site_va = None
            for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
                if raw_offset <= site < raw_offset + raw_size:
                    site_va = image_base + virtual_address + (site - raw_offset)
                    break
            if site_va is None:
                continue
            print(f"  push at {site_va:#x}")
            low = site_va - 0x70
            chunk = bytes(image[low - image_base:site_va + 0x30 - image_base])
            for insn in md.disasm(chunk, low):
                print(f"    {insn.address:#010x} {insn.mnemonic:8s} {insn.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
