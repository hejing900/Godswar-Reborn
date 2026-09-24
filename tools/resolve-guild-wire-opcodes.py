"""Resolve guild wire opcodes through the client's two-level dispatch.

The dispatcher at 0x4ea861 does:

    eax = wireOpcode - 10001
    if eax > 0xc6 -> default
    eax = byteTable[eax + 0x4ee900]      ; wire opcode -> case slot
    jmp dwordTable[eax * 4 + 0x4ee82c]   ; case slot -> handler

So a handler's wire opcodes are every byte-table index whose slot equals that
handler's slot. This prints the full wire-opcode map for the guild messages.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"
BYTE_TABLE = 0x004EE900
DWORD_TABLE = 0x004EE82C
BYTE_COUNT = 199          # cmp eax, 0xc6 -> 0..198
BASE_OPCODE = 10001
SLOT_COUNT = (BYTE_TABLE - DWORD_TABLE) // 4


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

    slots = [struct.unpack_from("<I", image, DWORD_TABLE - image_base + k * 4)[0]
             for k in range(SLOT_COUNT)]
    bytes_ = [image[BYTE_TABLE - image_base + i] for i in range(BYTE_COUNT)]

    print(f"{SLOT_COUNT} case slots, {BYTE_COUNT} wire opcodes mapped "
          f"({BASE_OPCODE}..{BASE_OPCODE + BYTE_COUNT - 1})\n")

    # Label each slot with the MSG_* name pushed inside its case body.
    order = sorted(range(SLOT_COUNT), key=lambda k: slots[k])
    labels = {}
    for position, slot in enumerate(order):
        target = slots[slot]
        limit = slots[order[position + 1]] if position + 1 < len(order) else None
        names = [text for site, text in sites
                 if target <= site and (limit is None or site < limit)
                 and site - target < 0x400]
        labels[slot] = sorted(set(names))

    print("wire  slot  case        message")
    for index in range(BYTE_COUNT):
        slot = bytes_[index]
        if slot >= SLOT_COUNT:
            continue
        names = labels.get(slot, [])
        if not any("CONSORTIA" in n or "ALTAR" in n for n in names):
            continue
        wire = BASE_OPCODE + index
        print(f"{wire:5d}  {slot:4d}  {slots[slot]:#010x}  {', '.join(names)}")

    print("\n=== every guild wire opcode, grouped by message ===")
    grouped = {}
    for index in range(BYTE_COUNT):
        slot = bytes_[index]
        for name in labels.get(slot, []):
            if "CONSORTIA" in name or "ALTAR" in name:
                grouped.setdefault(name, []).append(BASE_OPCODE + index)
                break
    for name in sorted(grouped):
        wires = grouped[name]
        print(f"  {name:34s} {wires[0]:5d}"
              + (f" .. {wires[-1]}" if len(wires) > 1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
