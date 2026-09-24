"""Map each guild window label to the CConsortia field it prints.

For every text key the client pushes the literal next to the field read, so
after locating the push the next `mov reg, [ebp+disp]` names the field. Combined
with SetConsortiaInfo's copy table (packet body offset -> CConsortia offset)
this yields the wire meaning of each field.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
KEYS = [
    "ConsortiaLevel",
    "MemberMax",
    "ConsortiaFunds",
    "ConsortiaBijou",
    "ConsortiaAltar",
    "OnlineNum",
    "MemberMax200",
    "ConsortiaAltarText",
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
            print(f"{key}: no literal")
            continue
        literal_va = va_of(literal, image_base, sections)
        sites = []
        cursor = 0
        needle = b"\x68" + struct.pack("<I", literal_va)
        while True:
            found = data.find(needle, cursor)
            if found < 0:
                break
            cursor = found + 1
            va = va_of(found, image_base, sections)
            if va is not None:
                sites.append(va)
        print(f"=== {key} (literal {literal_va:#x}), {len(sites)} push site(s)")
        for site in sites[:3]:
            low = site - 0x20
            high = site + 0xC0
            chunk = bytes(image[low - image_base:high - image_base])
            accesses = []
            for insn in md.disasm(chunk, low):
                text = f"{insn.mnemonic} {insn.op_str}"
                if "ebp + 0x" in text or "ebp - 0x" in text:
                    accesses.append(f"{insn.address:#010x} {text}")
            print(f"  push at {site:#x}; nearby frame accesses:")
            for line in accesses[:8]:
                print(f"    {line}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
