"""Hunt for the wire-opcode to internal-id mapping table.

Known wire opcodes with known declared lengths (taken from captured reference
traffic) are searched for as packed 32-bit pairs, in both field orders. A
packet table in the client would also list every other opcode with its length,
which is what makes the guild opcodes readable once one entry is located.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"

# (wire opcode, declared length) measured from captured reference traffic.
PAIRS = [
    (10015, 8),
    (10016, 40),
    (10017, 34),
    (10020, 108),
    (10022, 1524),
    (10023, 8),
    (10033, 888),
    (10038, 137),
    (10056, 40),
    (10067, 48),
    (10069, 92),
    (10070, 20),
    (10194, 0),
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


def va_of(offset, image_base, sections):
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        if raw_offset <= offset < raw_offset + raw_size:
            return image_base + virtual_address + (offset - raw_offset)
    return None


def main():
    data, image_base, sections = load_pe(EXE)
    for opcode, length in PAIRS:
        for order, packed in (
                ("opcode|len<<16", opcode | (length << 16)),
                ("len|opcode<<16", length | (opcode << 16)),
                ("u16 pair", None)):
            if packed is None:
                needle = struct.pack("<HH", opcode, length)
            else:
                needle = struct.pack("<I", packed)
            hits = []
            cursor = 0
            while True:
                found = data.find(needle, cursor)
                if found < 0:
                    break
                cursor = found + 1
                hits.append(found)
            if hits:
                print(f"opcode {opcode} len {length} as {order}: "
                      f"{len(hits)} hit(s)")
                for hit in hits[:3]:
                    va = va_of(hit, image_base, sections)
                    print(f"    file_off={hit:#x} va={va if va is None else hex(va)}")
                    context = data[hit - 24:hit + 40]
                    for line in range(0, len(context), 16):
                        row = context[line:line + 16]
                        print("      " + " ".join(f"{b:02x}" for b in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
