"""Find which struct fields feed the guild window's "current / max" numbers.

The window prints the member counts as one formatted line, so the format string
sits next to the two field reads that fill it. This locates candidate format
literals and disassembles their push sites.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
PATTERNS = [b"%d/%d\0", b"%d / %d\0", b"%d/%d ", b"%d:%d\0", b"%d/%d\\", b"/%d\0"]


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

    for pattern in PATTERNS:
        start = 0
        while True:
            found = data.find(pattern, start)
            if found < 0:
                break
            start = found + 1
            va = va_of(found, image_base, sections)
            if va is None or not (0x900000 <= va <= 0x9C0000):
                continue
            sites = []
            cursor = 0
            needle = b"\x68" + struct.pack("<I", va)
            while True:
                hit = data.find(needle, cursor)
                if hit < 0:
                    break
                cursor = hit + 1
                site = va_of(hit, image_base, sections)
                if site is not None and 0x530000 <= site <= 0x560000:
                    sites.append(site)
            print(f"=== {pattern!r} at {va:#x}: {len(sites)} guild-UI push site(s)")
            for site in sites[:2]:
                low = site - 0x70
                chunk = bytes(image[low - image_base:site + 0x30 - image_base])
                for insn in md.disasm(chunk, low):
                    print(f"   {insn.address:#010x}  {insn.mnemonic:8s} "
                          f"{insn.op_str}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
