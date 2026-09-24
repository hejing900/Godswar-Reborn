"""Read the shipped monster baseline artifact and report its real coverage.

MonsterContentBaseline.v1.gz is the reviewed content the server publishes; its
header is 'GWMONB01', then an int32 entry count, then fixed fields per row
(int16 mapId, length-prefixed strings, uint32 objectId, 2 floats, byte-array
packet). Parsing it directly answers "which maps does the server actually
publish monsters for", which a table count cannot.

Usage: python tools/read_monster_baseline.py
"""
from __future__ import annotations

import collections
import gzip
import hashlib
import pathlib
import struct
import sys

ARTIFACT = pathlib.Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Infrastructure\WorldContent"
    r"\Baselines\MonsterContentBaseline.v1.gz")
EXPECTED_ENTRY_COUNT = 2018
EXPECTED_ARTIFACT_SHA256 = (
    "676340AAD4DACE8C8A2914FBF37891AA9B61C00086EAA972ABE30714E5A1C9B6")


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def int32(self) -> int:
        value = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return value

    def int16(self) -> int:
        value = struct.unpack_from("<h", self.data, self.offset)[0]
        self.offset += 2
        return value

    def uint32(self) -> int:
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def single(self) -> float:
        value = struct.unpack_from("<f", self.data, self.offset)[0]
        self.offset += 4
        return value

    def blob(self) -> bytes:
        length = self.int32()
        value = self.data[self.offset:self.offset + length]
        self.offset += length
        return value

    def text(self) -> str:
        return self.blob().decode("utf-8")

    def fixed(self, length: int) -> bytes:
        value = self.data[self.offset:self.offset + length]
        self.offset += length
        return value


def main() -> int:
    raw = ARTIFACT.read_bytes()
    artifact_hash = hashlib.sha256(raw).hexdigest().upper()
    print(f"artifact      : {ARTIFACT.name} ({len(raw)} bytes)")
    print(f"sha256        : {artifact_hash}")
    print(f"matches pinned: {artifact_hash == EXPECTED_ARTIFACT_SHA256}")

    data = gzip.decompress(raw)
    reader = Reader(data)
    magic = reader.fixed(8)
    count = reader.int32()
    print(f"magic         : {magic!r}")
    print(f"entry count   : {count} "
          f"(code expects {EXPECTED_ENTRY_COUNT}, "
          f"{'ok' if count == EXPECTED_ENTRY_COUNT else 'MISMATCH'})")

    per_map = collections.Counter()
    templates: dict[int, set[str]] = collections.defaultdict(set)
    for _ in range(count):
        map_id = reader.int16()
        reader.text()               # sceneKey
        template = reader.text()
        reader.text()               # displayName
        reader.uint32()             # objectId
        reader.single()             # x
        reader.single()             # z
        reader.blob()               # packet
        per_map[map_id] += 1
        templates[map_id].add(template)

    print(f"\nconsumed bytes: {reader.offset} / {len(data)} "
          f"({'exact' if reader.offset == len(data) else 'TRAILING DATA'})")
    print(f"\n{'map':>4} {'monsters':>9} {'templates':>10}")
    for map_id in sorted(per_map):
        print(f"{map_id:>4} {per_map[map_id]:>9} {len(templates[map_id]):>10}")

    for map_id in (3, 11, 18):
        found = sorted(templates.get(map_id, set()))
        print(f"\nmap {map_id} templates ({len(found)}):")
        for template in found:
            print(f"    {template}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
