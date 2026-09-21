"""Audited x86 display-only title bracket color wrapper and cave guards."""
import json
from pathlib import Path
import struct

from holy_suit_tiers.text import PatchError

CAVE_OFFSET = 0x5C3F20
CAVE_VA = 0x9C3F20
CAVE_LENGTH = 128
RETIRED_HOOK_OFFSET = 0x1B5B97
RETIRED_HOOK = bytes.fromhex("A1AC5E5701")
RETIRED_PREFIX = bytes.fromhex(
    "683C44950052FFD78B8E5C0100008B018B808400000083C40C8D54242852FFD0")
RETIRED_SUFFIX = bytes.fromhex(
    "80B88C07000002754468080200008D4C242C516AFF058D070000506A006A00FF")
# ESI/EDI are saved; the original EDX destination and two stack arguments
# are passed to 402DF0. EAX retains the stock formatter's return length.
# After complete prefix/reset checks, two bounded ten-byte rotations place
# both brackets inside the color span. No catalog or shared string is edited.
PROFILE = json.loads(Path(__file__).with_name("TitleBracketColorNative.json").read_text())
CODE = bytes.fromhex(PROFILE["code_hex"])
CAVE = CODE + bytes(CAVE_LENGTH - len(CODE))
ENTRY = bytes.fromhex(PROFILE["entry_hex"])


def validate_cave_mapping(data: bytes) -> None:
    """Require the mapped executable section and disabled historical hook."""
    try:
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        machine, count = struct.unpack_from("<HH", data, pe + 4)
        size = struct.unpack_from("<H", data, pe + 20)[0]
        optional = pe + 24
        if data[pe:pe + 4] != b"PE\0\0" or machine != 0x14C or not 1 <= count <= 16 or \
                struct.unpack_from("<H", data, optional)[0] != 0x10B or \
                struct.unpack_from("<I", data, optional + 28)[0] != 0x400000:
            raise PatchError("Title cave requires the audited x86 PE32 image")
        mapped = False
        for index in range(count):
            section = optional + size + index * 40
            va, raw_size, raw = struct.unpack_from("<III", data, section + 12)
            flags = struct.unpack_from("<I", data, section + 36)[0]
            if raw <= CAVE_OFFSET and CAVE_OFFSET + CAVE_LENGTH <= raw + raw_size:
                mapped = data[section:section + 8].rstrip(b"\0") == b".rdata" and \
                    bool(flags & 0x20000000) and 0x400000 + va + CAVE_OFFSET - raw == CAVE_VA
        if not mapped:
            raise PatchError("Title cave is outside the audited executable .rdata mapping")
    except (struct.error, IndexError) as error:
        raise PatchError("Title cave PE metadata is invalid") from error
    for pin in PROFILE["required_pins"]:
        offset, expected = int(pin["offset"], 16), bytes.fromhex(pin["hex"])
        if data[offset:offset + len(expected)] != expected:
            raise PatchError(f"Title/retired speed prerequisite differs at 0x{offset:X}")


def validate_cave_references(data: bytes, installed: bool) -> None:
    """Reject direct/absolute references from any former or foreign cave owner."""
    inbound = []
    low, high = CAVE_VA, CAVE_VA + CAVE_LENGTH
    # Both established executable sections have file offset == RVA.
    for offset in range(0x1000, 0x5C4000 - 5):
        opcode = data[offset]
        if opcode in (0xE8, 0xE9):
            target = 0x400000 + offset + 5 + struct.unpack_from("<i", data, offset + 1)[0]
            if low <= target < high:
                inbound.append((offset, target))
        elif opcode == 0x0F and 0x80 <= data[offset + 1] <= 0x8F:
            target = 0x400000 + offset + 6 + struct.unpack_from("<i", data, offset + 2)[0]
            if low <= target < high:
                inbound.append((offset, target))
    if inbound != ([(0x20921, CAVE_VA)] if installed else []):
        raise PatchError("Title cave has foreign or partial inbound code references")
    for target in range(low, high):
        if struct.pack("<I", target) in data:
            raise PatchError("Title cave has an absolute pointer reference")
