"""Label the whole client message dispatch table with its MSG_* names.

The master dispatcher subtracts 0x2711 (10001) from the received opcode and
jumps through a 199-entry table at 0x4ee82c. Each entry lands on a case body
that pushes the message's MSG_* name, so pairing entries with the name pushes
inside each case yields the opcode-to-message mapping. Known opcodes from the
server (NPC dialog 10067, mall 10178, ...) cross-check the result.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"
TABLE_VA = 0x004EE82C
BASE_OPCODE = 10001
ENTRY_COUNT = 199


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


def collect_name_pushes(data, image_base, sections):
    """Every `push offset "MSG_..."` site, as (name, push_va)."""
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
        # virtual address of the string literal
        string_va = None
        for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
            if raw_offset <= index < raw_offset + raw_size:
                string_va = image_base + virtual_address + (index - raw_offset)
                break
        if string_va is None:
            continue
        needle = b"\x68" + struct.pack("<I", string_va)
        cursor = 0
        while True:
            found = data.find(needle, cursor)
            if found < 0:
                break
            cursor = found + 1
            for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
                if raw_offset <= found < raw_offset + raw_size:
                    sites.append((image_base + virtual_address
                                  + (found - raw_offset), text))
                    break
    return sorted(sites)


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)
    sites = collect_name_pushes(data, image_base, sections)
    print(f"{len(sites)} message-name reference sites\n")

    entries = []
    for index in range(ENTRY_COUNT):
        target = struct.unpack_from(
            "<I", image, TABLE_VA - image_base + index * 4)[0]
        entries.append(target)

    # A case body owns every name push that follows it until the next entry.
    ordered = sorted(zip(entries, range(ENTRY_COUNT)))
    labels = {}
    for position, (target, index) in enumerate(ordered):
        limit = ordered[position + 1][0] if position + 1 < len(ordered) else None
        names = [text for site, text in sites
                 if target <= site and (limit is None or site < limit)
                 and site - target < 0x400]
        labels[index] = names

    print("opcode  entry      case        message names")
    for index in range(ENTRY_COUNT):
        opcode = BASE_OPCODE + index
        names = labels[index]
        joined = ", ".join(sorted(set(names))) if names else "-"
        print(f"{opcode:6d}  {entries[index]:#010x}  {joined}")

    print("\n=== consortia opcodes ===")
    for index in range(ENTRY_COUNT):
        names = labels[index]
        if any("CONSORTIA" in name or "ALTAR" in name for name in names):
            print(f"  {BASE_OPCODE + index:6d}  "
                  f"{entries[index]:#010x}  {', '.join(sorted(set(names)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
