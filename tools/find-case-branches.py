"""Read the opcode comparisons that select each consortia message case.

The consortia case bodies sit in one contiguous region of the player message
handler, so the dispatcher selects them with an if/else chain rather than a
jump table. Every branch that targets a case records the opcode in the
comparison immediately before it, so this walks the .text section looking for
jumps into the case region and prints the preceding instructions.
"""

import struct
import sys

EXE = r"D:\Godswar Origin\Origin.exe"

# Case-name reference sites found by find-dispatch-table.py: (name, push VA)
CASES = [
    ("MSG_CONSORTIA_INVITE", 0x4ED2A4),
    ("MSG_CONSORTIA_INVITE#2", 0x4ED3DC),
    ("MSG_CONSORTIA_EXIT", 0x4ED4DF),
    ("MSG_CONSORTIA_TEXT", 0x4ED670),
    ("MSG_CONSORTIA_DISMISS", 0x4ED69D),
    ("MSG_CONSORTIA_DUTY", 0x4ED78F),
    ("MSG_CONSORTIA_MEMBER_DEL", 0x4ED882),
    ("MSG_CONSORTIA_RESPONSE", 0x4EDA24),
    ("MSG_CONSORTIA_BASE_INFO", 0x4EDA3B),
    ("MSG_CONSORTIA_MEMBER_LIST", 0x4EDB5D),
    ("MSG_CONSORTIA_MEMBER_ONE", 0x4EDC77),
    ("MSG_CONSORTIA_CREATE_RESPONSE", 0x4ECDA3),
    ("MSG_CONSORTIA_NOTE", 0x4EDF46),
    ("MSG_ALTAR_INFO", 0x4EDF0C),
    ("MSG_CONSORTIA_ELEMENT_LIST", 0x4EDFC6),
    ("MSG_CONSORTIA_MEMBER_ADD_MSG", 0x4DF151),
]

WINDOW_BACK = 0x60
WINDOW_FORWARD = 0x10


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
    _, text_va, _, text_off, text_size = text
    text_base = image_base + text_va

    # Decode every relative branch in .text once.
    branches = []
    offset = text_off
    end = text_off + text_size - 6
    while offset < end:
        opcode = data[offset]
        if opcode == 0xE9:
            rel = struct.unpack_from("<i", data, offset + 1)[0]
            site = text_base + (offset - text_off)
            branches.append((site, site + 5 + rel, 5, "jmp"))
            offset += 5
            continue
        if opcode == 0x0F and 0x80 <= data[offset + 1] <= 0x8F:
            rel = struct.unpack_from("<i", data, offset + 2)[0]
            site = text_base + (offset - text_off)
            branches.append((site, site + 6 + rel, 6, "jcc"))
            offset += 6
            continue
        offset += 1

    print(f"{len(branches)} relative branches decoded\n")

    for name, push_va in CASES:
        low = push_va - WINDOW_BACK
        high = push_va + WINDOW_FORWARD
        matches = [b for b in branches if low <= b[1] <= high]
        print(f"=== {name} (case around {push_va:#x})")
        if not matches:
            print("   no branch targets this region")
            continue
        for site, target, length, kind in matches:
            print(f"   {kind} at {site:#x} -> {target:#x}"
                  f" (case start {target - push_va:+#x} from name ref)")
            start = max(text_off, text_off + (site - text_base) - 0x30)
            chunk = data[start:start + 0x30 + length]
            for line in range(0, len(chunk), 16):
                row = chunk[line:line + 16]
                va = text_base + (start + line - text_off)
                print(f"      {va:#010x}  " + " ".join(f"{b:02x}" for b in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
