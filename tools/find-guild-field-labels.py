"""Tie each guild struct field to the label the window shows it under.

The client pushes a text key next to the code that reads the field, so finding
the push sites of ConsortiaLevel / MemberMax / ConsortiaFunds / ConsortiaBijou /
ConsortiaAltar / OnlineNum and disassembling around them reveals which struct
offset each label renders.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
KEYS = [
    "ConsortiaLevel",
    "MemberMax",
    "ConsortiaFunds",
    "ConsortiaBijou",
    "ConsortiaAltar",
    "OnlineNum",
    "Contribute",
    "Profession",
    "Job",
]


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


def va_of(offset, image_base, sections):
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        if raw_offset <= offset < raw_offset + raw_size:
            return image_base + virtual_address + (offset - raw_offset)
    return None


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.skipdata = True

    for key in KEYS:
        needle = key.encode("ascii") + b"\0"
        hits = []
        start = 0
        while True:
            found = data.find(needle, start)
            if found < 0:
                break
            start = found + 1
            hits.append((found, va_of(found, image_base, sections)))
        print(f"=== {key}: {len(hits)} literal(s)")
        for offset, va in hits[:2]:
            print(f"    literal at {va:#x}")
            branches = b"\x68" + struct.pack("<I", va)
            cursor = 0
            while True:
                site = data.find(branches, cursor)
                if site < 0:
                    break
                cursor = site + 1
                site_va = va_of(site, image_base, sections)
                if site_va is None:
                    continue
                print(f"      push at {site_va:#x}")
                low = site_va - 0x60
                chunk = bytes(image[low - image_base:
                                    site_va + 0x40 - image_base])
                for insn in md.disasm(chunk, low):
                    print(f"        {insn.address:#010x}  "
                          f"{insn.mnemonic:8s} {insn.op_str}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
