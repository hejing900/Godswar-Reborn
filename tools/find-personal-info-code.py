"""Locate CPersonalInfoUI::UpdatePersonalInfo by its control names.

PersonalInfoUI.xml names its value controls DutyText / UnionText, and the C++
panel writes into them by name, so those literals sit inside the update
function. Printing the pushes finds the code that fills the 职位 row.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
KEYS = ("DutyText", "UnionText", "ContributeText", "PersonalInfoUI", "PersonalInfo")


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
        literal = data.find(key.encode("ascii") + b"\0")
        if literal < 0:
            print(f'=== "{key}": not found')
            continue
        literal_va = va_of(literal, image_base, sections)
        print(f'=== "{key}": literal at {literal_va:#x}')
        needle = b"\x68" + struct.pack("<I", literal_va)
        cursor = 0
        count = 0
        while True:
            site = data.find(needle, cursor)
            if site < 0:
                break
            cursor = site + 1
            count += 1
            site_va = va_of(site, image_base, sections)
            if site_va is None or count > 3:
                continue
            print(f"  push at {site_va:#x}")
            low = site_va - 0x40
            for insn in md.disasm(
                    bytes(image[low - image_base:site_va + 0x18 - image_base]),
                    low):
                print(f"    {insn.address:#010x} {insn.mnemonic:8s} "
                      f"{insn.op_str}")
        print(f"  total {count} push site(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
