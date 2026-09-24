"""Dump one 88-byte record from the captured mall / bound-gold shop catalogs.

Usage:
  python tools/dump_shop_record.py mall 8 0
  python tools/dump_shop_record.py boundgold 3 1
"""
from __future__ import annotations

import base64
import gzip
import re
import struct
import sys
from pathlib import Path

SOURCES = {
    "mall": (
        Path(
            r"D:\Godswar-Reborn-main\src\Godswar.Server\Packets"
            r"\PacketBuilder.MallCatalog.cs"
        ),
        8,
    ),
    "boundgold": (
        Path(
            r"D:\Godswar-Reborn-main\src\Godswar.Server\Packets"
            r"\PacketBuilder.CapitalNpcShops.cs"
        ),
        16,
    ),
}


def load(kind: str) -> tuple[bytes, int]:
    path, header = SOURCES[kind]
    text = path.read_text(encoding="utf-8")
    if kind == "mall":
        blob = re.findall(
            r"private const string \w+Gzip =(.*?);", text, re.S
        )[0]
    else:
        blob = re.search(
            r"private const string BoundGoldVendorCatalogGzip =(.*?);",
            text,
            re.S,
        ).group(1)
    b64 = "".join(re.findall(r'"([A-Za-z0-9+/=]*)"', blob))
    return gzip.decompress(base64.b64decode(b64)), header


def main() -> int:
    kind = sys.argv[1]
    wanted = int(sys.argv[2])
    slot = int(sys.argv[3])
    data, header = load(kind)
    offset = 0
    frame = 0
    while offset + header <= len(data):
        length = struct.unpack_from("<H", data, offset)[0]
        frame += 1
        if frame == wanted:
            count = (length - header) // 88
            print(
                f"{kind} frame {frame}: len={length} header={header} "
                f"count={count}"
            )
            for index in range(count):
                ro = offset + header + index * 88
                record = data[ro : ro + 88]
                if slot >= 0 and index != slot:
                    continue
                words = struct.unpack_from("<22I", record, 0)
                print(f"  slot {index} itemId={words[0]}")
                print("    hex   = " + record.hex(" "))
                print("    words = " + " ".join(str(w) for w in words))
            break
        offset += length
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
