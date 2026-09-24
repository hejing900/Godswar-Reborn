"""Look for a message table that pairs opcodes with the MSG_* names.

The image contains a pool of 81 MSG_* message names. If the client keeps a
per-opcode table (opcode -> name and/or handler), each name's virtual address
appears as a little-endian dword inside that table. Finding those references
and dumping the entries around them recovers the opcode-to-message mapping.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"
PREFIX = b"MSG_"


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


def va_of(offset, image_base, sections):
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        if raw_offset <= offset < raw_offset + raw_size:
            return image_base + virtual_address + (offset - raw_offset)
    return None


def offset_of(va, image_base, sections):
    rva = va - image_base
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            delta = rva - virtual_address
            return raw_offset + delta if delta < raw_size else None
    return None


def main():
    data, image_base, sections = load_pe(EXE)

    # Collect the MSG_* strings and their virtual addresses.
    messages = []
    start = 0
    while True:
        index = data.find(PREFIX, start)
        if index < 0:
            break
        start = index + 1
        end = index
        while end < len(data) and 32 <= data[end] < 127:
            end += 1
        if data[end] == 0:
            text = data[index:end].decode("ascii")
            va = va_of(index, image_base, sections)
            if va is not None and text.startswith("MSG_"):
                messages.append((text, va, index))
    unique = {}
    for text, va, index in messages:
        unique.setdefault(text, (va, index))
    print(f"found {len(messages)} MSG_* string occurrences, "
          f"{len(unique)} distinct")
    for text in sorted(unique):
        if "CONSORTIA" in text:
            print(f"  {text:48s} va={unique[text][0]:#010x}")

    # Look for dword references to each name.
    print("\n=== pointer references to MSG_* names ===")
    referenced = []
    for text, (va, index) in sorted(unique.items()):
        needle = struct.pack("<I", va)
        hits = []
        cursor = 0
        while True:
            found = data.find(needle, cursor)
            if found < 0:
                break
            cursor = found + 1
            hits.append(found)
        if hits:
            referenced.append((text, va, hits))
    if not referenced:
        print("  none")
    for text, va, hits in referenced:
        print(f"  {text} -> {len(hits)} reference(s)")
        for hit in hits[:4]:
            print(f"     at file_off={hit:#x} va={va_of(hit, image_base, sections)}")
            context = data[max(0, hit - 32):hit + 32]
            for line in range(0, len(context), 16):
                row = context[line:line + 16]
                print("       " + " ".join(f"{b:02x}" for b in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
