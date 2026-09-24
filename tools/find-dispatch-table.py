"""Recover opcodes by matching MSG_* case bodies against the dispatch table.

Each MSG_* name string is referenced exactly once, from inside the code that
handles that message. A switch dispatcher reaches those case bodies through a
jump table, so a little-endian dword pointing at (or just before) the string
reference is a jump-table entry. Dumping the table around each hit exposes the
entry index, and known opcodes on neighbouring entries calibrate the base.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"
WANTED = ("CONSORTIA", "UNION", "ALTAR")


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


def find_message_sites(data, image_base, sections):
    sites = []
    start = 0
    while True:
        index = data.find(b"MSG_", start)
        if index < 0:
            break
        start = index + 1
        end = index
        while end < len(data) and 32 <= data[end] < 127:
            end += 1
        if data[end] != 0:
            continue
        text = data[index:end].decode("ascii")
        va = va_of(index, image_base, sections)
        if va is None:
            continue
        # The reference is `push imm32` (68 <va>) five bytes before the call.
        needle = b"\x68" + struct.pack("<I", va)
        cursor = 0
        while True:
            found = data.find(needle, cursor)
            if found < 0:
                break
            cursor = found + 1
            sites.append((text, va, found, va_of(found, image_base, sections)))
    return sites


def main():
    data, image_base, sections = load_pe(EXE)
    sites = find_message_sites(data, image_base, sections)
    print(f"{len(sites)} message-name reference sites")

    interesting = [s for s in sites
                   if any(token in s[0] for token in WANTED)]
    print(f"{len(interesting)} consortia/altar sites\n")

    for text, string_va, file_off, push_va in sorted(interesting):
        print(f"=== {text}  push_va={push_va:#x}")
        # Look for jump-table entries pointing into the twenty instructions
        # that precede the name reference.
        hits = []
        for back in range(0, 0x80, 4):
            candidate = push_va - back
            if candidate < image_base:
                continue
            needle = struct.pack("<I", candidate)
            cursor = 0
            while True:
                found = data.find(needle, cursor)
                if found < 0:
                    break
                cursor = found + 1
                where = va_of(found, image_base, sections)
                if where is None:
                    continue
                # Jump tables live in .rdata/.data, never inside .text code.
                section = next((s for s in sections
                                if s[3] <= found < s[3] + s[4]), None)
                if section and section[0] in (".rdata", ".data"):
                    hits.append((back, candidate, found, where, section[0]))
        if not hits:
            print("  no table entry found\n")
            continue
        for back, candidate, found, where, section in hits[:3]:
            print(f"  entry {where:#x} in {section} points at push-{back:#x} "
                  f"({candidate:#x})")
            context = data[found - 32:found + 40]
            for line in range(0, len(context), 16):
                row = context[line:line + 16]
                print("     " + " ".join(f"{b:02x}" for b in row))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
