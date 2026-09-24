"""Find handler-table entries that reference the consortia handlers.

A direct `call rel32` to CPlayer::SetConsortiaInfo / _CreateConsortiaSuccess
does not exist, so the client dispatches messages through a table of function
pointers. This scans the whole image for the little-endian addresses and dumps
the surrounding bytes, which is where the opcode that selects each handler is
stored.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"

TARGETS = {
    0x00701780: "SetConsortiaInfo(MSG_CONSORTIA_BASE_INFO*)",
    0x007019E0: "_CreateConsortiaSuccess(MSG_CONSORTIA_CREATE_RESPONSE*)",
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
    sections = []
    table = optional + optional_size
    for index in range(section_count):
        entry = table + (index * 40)
        name = data[entry:entry + 8].rstrip(b"\0").decode("ascii", "replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, entry + 8)
        sections.append((name, virtual_address, virtual_size, raw_offset, raw_size))
    return data, image_base, sections


def main():
    data, image_base, sections = load_pe(EXE)
    for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
        print(f"section {name:8s} va={image_base + virtual_address:#010x} "
              f"raw={raw_offset:#08x} size={raw_size:#x}")
    for target, label in TARGETS.items():
        needle = struct.pack("<I", target)
        print(f"\n=== {label} ({target:#x}) ===")
        found = 0
        start = 0
        while True:
            index = data.find(needle, start)
            if index < 0:
                break
            start = index + 1
            found += 1
            # Map file offset back to a virtual address for readability.
            va = None
            for name, virtual_address, virtual_size, raw_offset, raw_size in sections:
                if raw_offset <= index < raw_offset + raw_size:
                    va = image_base + virtual_address + (index - raw_offset)
                    break
            context_start = max(0, index - 48)
            context = data[context_start:index + 48]
            print(f"  hit #{found} file_off={index:#x} va={va if va is None else hex(va)}")
            for line in range(0, len(context), 16):
                row = context[line:line + 16]
                hexed = " ".join(f"{byte:02x}" for byte in row)
                print(f"      {hexed}")
        if found == 0:
            print("  no pointer reference found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
