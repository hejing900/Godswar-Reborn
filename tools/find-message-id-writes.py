"""Find where the network layer stamps the internal message id.

The dispatcher reads the message id from [message+6], so the receive path
converts the wire opcode into that internal id somewhere. This scans for
instructions that write a 16-bit value to [reg+6] and prints each site with
its surrounding code so the conversion (table or comparison chain) is visible.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"


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
    code = bytes(image[text_rva:text_rva + text_size])

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True

    sites = []
    for insn in md.disasm(code, text_start):
        text_form = f"{insn.mnemonic} {insn.op_str}"
        # looking for a 16-bit store into [something + 6]
        if not (text_form.startswith("mov") and "word ptr" in text_form):
            continue
        if "+ 6]" not in text_form:
            continue
        sites.append((insn.address, insn.bytes.hex(), text_form))

    print(f"{len(sites)} word stores into [reg+6]\n")
    for address, raw, text_form in sites[:200]:
        print(f"  {address:#010x}  {raw:<22s} {text_form}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
