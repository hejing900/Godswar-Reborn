"""Map the real jump tables in the dispatcher's table region.

The region around 0x4ee800 mixes several tables, so this prints every run of
consecutive dwords that look like code addresses together with its length, and
dumps the surrounding bytes, so the table the `cmp eax, 0xc6` bound belongs to
can be identified exactly.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"
LOW = 0x004EE700
HIGH = 0x004EEC00


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
    text_start = image_base + text_rva
    text_end = text_start + text_size

    print("runs of dwords that look like .text addresses:")
    va = LOW
    while va < HIGH:
        value = struct.unpack_from("<I", image, va - image_base)[0]
        if text_start <= value < text_end:
            start = va
            count = 0
            while va < HIGH:
                value = struct.unpack_from("<I", image, va - image_base)[0]
                if not (text_start <= value < text_end):
                    break
                va += 4
                count += 1
            print(f"  {start:#010x} .. {va - 4:#010x}  {count} entries")
            for slot in range(count):
                entry = struct.unpack_from(
                    "<I", image, start - image_base + slot * 4)[0]
                if slot < 6 or count - slot <= 3:
                    print(f"      [{slot:3d}] {entry:#010x}")
        else:
            va += 4

    print("\nraw bytes 0x4ee820..0x4ee940:")
    for line in range(LOW + 0x120, LOW + 0x240, 16):
        row = image[line - image_base:line - image_base + 16]
        print(f"  {line:#010x}  " + " ".join(f"{b:02x}" for b in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
