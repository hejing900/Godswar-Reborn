"""Inspect the bytes the linker map attributes to the consortia handlers.

If the image is packed, the mapped function bodies will not look like code;
this prints them plus a quick entropy picture of .text so that conclusion is
measured rather than assumed.
"""

import math
import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"

ADDRESSES = {
    0x00701780: "SetConsortiaInfo",
    0x007019E0: "_CreateConsortiaSuccess",
    0x006FE110: "CPlayer::CreateConsortia(const char*)",
    0x0069B430: "ConsortiaVisible(HotKey.obj)",
}


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
    entry_point = struct.unpack_from("<I", data, optional + 16)[0]
    sections = []
    table = optional + optional_size
    for index in range(section_count):
        entry = table + (index * 40)
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii", "replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, entry + 8)
        sections.append((name, virtual_address, virtual_size, raw_offset, raw_size))
    return data, image_base, sections, entry_point


def offset_of(va, image_base, sections):
    rva = va - image_base
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            delta = rva - virtual_address
            return raw_offset + delta if delta < raw_size else None
    return None


def entropy(chunk):
    if not chunk:
        return 0.0
    counts = [0] * 256
    for byte in chunk:
        counts[byte] += 1
    total = len(chunk)
    return -sum((count / total) * math.log2(count / total)
                for count in counts if count)


def main():
    data, image_base, sections, entry_point = load_pe(EXE)
    print(f"entry point rva {entry_point:#x} (va {image_base + entry_point:#x})")
    text = next(s for s in sections if s[0] == ".text")
    name, text_va, text_vsize, text_off, text_size = text
    sample = data[text_off:text_off + text_size]
    print(f".text entropy (whole) = {entropy(sample):.3f} bits/byte")
    for label, chunk in (("head", sample[:0x4000]),
                         ("middle", sample[len(sample) // 2:len(sample) // 2 + 0x4000])):
        print(f".text entropy ({label}) = {entropy(chunk):.3f} bits/byte")
    entry_off = offset_of(image_base + entry_point, image_base, sections)
    if entry_off:
        head = data[entry_off:entry_off + 64]
        print("entry bytes:", " ".join(f"{b:02x}" for b in head))
    for va, label in ADDRESSES.items():
        offset = offset_of(va, image_base, sections)
        print(f"\n{label} @ {va:#x} file_off={offset if offset is None else hex(offset)}")
        if offset is None:
            print("  not mapped")
            continue
        chunk = data[offset:offset + 96]
        for line in range(0, len(chunk), 16):
            row = chunk[line:line + 16]
            print("   ", " ".join(f"{b:02x}" for b in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
