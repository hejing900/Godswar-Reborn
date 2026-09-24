"""Find indirect stores into the panel's pointer slot.

Writes through a computed address (`lea edx, [eax+0x2A4]` then `mov [edx], ecx`)
are invisible to a displacement-based scan, and that is exactly how a client
installs a structure pointer. This tracks addresses taken with `lea` for the
slot offset and reports any store through that register shortly afterwards.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

EXE = r"D:\Godswar Origin\Origin.exe"
SLOT_FROM_BASE = 0x2A4
SLOT_FROM_BLOCK = 0x48       # 0x2A4 - 0x25C, for code based on the block start
WINDOW = 0x8000
LOOKAHEAD = 12               # instructions the address may stay live


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
    start = image_base + text_rva
    code = bytes(image[text_rva:text_rva + text_size])

    hits = []
    for window in range(0, text_size, WINDOW):
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        md.skipdata = True
        live = {}          # register -> instructions remaining
        for insn in md.disasm(code[window:window + WINDOW], start + window):
            if insn.id == 0:
                continue
            try:
                operands = insn.operands
            except Exception:
                continue
            if not operands:
                continue
            for register in list(live):
                live[register] -= 1
                if live[register] < 0:
                    del live[register]

            dst = operands[0]
            if insn.mnemonic == "lea" and dst.type == CS_OP_REG \
                    and operands[1].type == CS_OP_MEM \
                    and operands[1].mem.disp in (SLOT_FROM_BASE, SLOT_FROM_BLOCK) \
                    and operands[1].mem.index == 0:
                live[dst.reg] = LOOKAHEAD
                continue

            if dst.type == CS_OP_MEM and dst.mem.base in live \
                    and dst.mem.disp == 0 and insn.mnemonic in (
                        "mov", "movzx", "movsx", "and", "or", "add", "sub"):
                hits.append((insn.address, f"{insn.mnemonic} {insn.op_str}",
                             insn.mnemonic))

    print(f"{len(hits)} indirect stores into the slot")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.skipdata = True
    for address, text_form, _ in hits[:20]:
        print(f"\n--- {address:#x}  {text_form}")
        low = address - 0x50
        for insn in md.disasm(
                bytes(image[low - image_base:address + 8 - image_base]), low):
            marker = "  <== STORE" if insn.address == address else ""
            print(f"    {insn.address:#010x}  {insn.mnemonic:8s} "
                  f"{insn.op_str}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
