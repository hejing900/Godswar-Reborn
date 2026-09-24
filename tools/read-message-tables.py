"""Read the message jump tables and map entries onto the consortia cases.

The dispatcher is a chain of indexed jumps whose tables live inside .text.
Each table has a base opcode taken from the `cmp`/`sub` right before the jump,
so an entry index converts straight into a wire opcode.
"""

import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"D:\Godswar Origin\Origin.exe"

# (dispatch site, table base VA, opcode of entry 0, note)
TABLES = [
    (0x004EA51A, 0x004EE814, 10000, "cmp eax,0x2710"),
    (0x004EA878, 0x004EE82C, 10001, "sub eax,0x2711"),
    (0x004EAF4B, 0x004EE9C8, None, "ecx indexed, base unknown"),
    (0x004EBCE6, 0x004EE9F4, None, "eax indexed, base unknown"),
    (0x004ECDDE, 0x004EEA04, None, "ecx indexed, base unknown"),
    (0x004EE3CD, 0x004EEA18, 10328, "sub eax,0x2858"),
]

CASES = [
    ("MSG_CONSORTIA_CREATE_RESPONSE", 0x4ECDA3),
    ("MSG_CONSORTIA_INVITE", 0x4ED2A4),
    ("MSG_CONSORTIA_EXIT", 0x4ED4DF),
    ("MSG_CONSORTIA_TEXT", 0x4ED670),
    ("MSG_CONSORTIA_DISMISS", 0x4ED69D),
    ("MSG_CONSORTIA_DUTY", 0x4ED78F),
    ("MSG_CONSORTIA_MEMBER_DEL", 0x4ED882),
    ("MSG_CONSORTIA_RESPONSE", 0x4EDA24),
    ("MSG_CONSORTIA_BASE_INFO", 0x4EDA3B),
    ("MSG_CONSORTIA_MEMBER_LIST", 0x4EDB5D),
    ("MSG_CONSORTIA_MEMBER_ONE", 0x4EDC77),
    ("MSG_CONSORTIA_NOTE", 0x4EDF46),
    ("MSG_ALTAR_INFO", 0x4EDF0C),
    ("MSG_CONSORTIA_ELEMENT_LIST", 0x4EDFC6),
    ("MSG_CONSORTIA_MEMBER_ADD_MSG", 0x4DF151),
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


def main():
    data, image_base, sections = load_pe(EXE)
    image = build_image(data, image_base, sections)

    for site, table_va, base_opcode, note in TABLES:
        print(f"=== dispatch {site:#x} table {table_va:#x} ({note})")
        for index in range(0, 80):
            raw = struct.unpack_from("<i", image, table_va - image_base + index * 4)[0]
            absolute = raw
            relative_to_table = table_va + raw
            label = None
            for name, target in CASES:
                if target - 0x100 <= absolute <= target + 0x10:
                    label = f"{name} (absolute)"
                    break
                if target - 0x100 <= relative_to_table <= target + 0x10:
                    label = f"{name} (rel to table)"
                    break
            if label is None and index > 40:
                break
            opcode = None if base_opcode is None else base_opcode + index
            shown = f"{opcode}" if opcode is not None else "?"
            print(f"   [{index:3d}] raw={raw:#010x} abs={absolute:#010x} "
                  f"rel={relative_to_table:#010x} opcode={shown}"
                  + (f"   <-- {label}" if label else ""))
        print()

    # Print the instructions just before each dispatch so the base is visible.
    text = next(s for s in sections if s[0] == ".text")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for site, table_va, base_opcode, note in TABLES:
        back = site - 0x40
        chunk = bytes(image[back - image_base:site + 8 - image_base])
        print(f"--- before {site:#x} ---")
        for insn in md.disasm(chunk, back):
            if insn.address > site:
                break
            print(f"   {insn.address:#010x}  {insn.mnemonic:8s} {insn.op_str}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
