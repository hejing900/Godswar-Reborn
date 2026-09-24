"""Find the receive path that calls the message dispatcher.

The dispatcher at 0x4ea3d0 reads its message id from [message+6]. Whoever calls
it therefore performs the wire-opcode to internal-id conversion, either through
a lookup table or a comparison chain, and that is the mapping needed to build
guild packets the stock client accepts.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"
DISPATCH = 0x004EA3D0


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
    text = next(s for s in sections if s[0] == ".text")
    _, text_rva, _, text_off, text_size = text
    text_base = image_base + text_rva

    hits = []
    offset = text_off
    end = text_off + text_size - 5
    while offset < end:
        if data[offset] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, offset + 1)[0]
            site = text_base + (offset - text_off)
            if site + 5 + rel == DISPATCH:
                hits.append((site, data[offset]))
        offset += 1
    print(f"{len(hits)} references to {DISPATCH:#x}")

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for site, opcode in hits:
        print(f"\n--- {'call' if opcode == 0xE8 else 'jmp'} at {site:#x}")
        low = site - 0xC0
        chunk = bytes(data[text_off + (low - text_base):
                           text_off + (site - text_base) + 5])
        for insn in md.disasm(chunk, low):
            print(f"  {insn.address:#010x}  {insn.bytes.hex():<20s} "
                  f"{insn.mnemonic:8s} {insn.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
