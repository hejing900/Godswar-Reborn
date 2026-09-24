"""Decode the captured capital-shop catalog blobs and list their stock items.

The three catalogs in PacketBuilder.CapturedCapitalNpcShops.cs are gzip-compressed
opcode-10071 streams captured from the reference server. This tool inflates them
and walks the shop-record layout so the stock can be compared against what the
runtime item catalog publishes.

Usage:
  python tools/decode_shop_catalog.py
"""
from __future__ import annotations

import base64
import gzip
import re
import struct
from pathlib import Path

SOURCE = Path(
    r"D:\Godswar-Reborn-main\src\Godswar.Server\Packets"
    r"\PacketBuilder.CapturedCapitalNpcShops.cs"
)


def load_blobs() -> dict[str, bytes]:
    text = SOURCE.read_text(encoding="utf-8")
    blobs: dict[str, bytes] = {}
    for name, literal in re.findall(
        r"private const string (\w+Gzip) =\s*\"([A-Za-z0-9+/=]+)\";", text
    ):
        blobs[name] = gzip.decompress(base64.b64decode(literal))
    return blobs


def walk(data: bytes, label: str) -> None:
    print(f"\n===== {label}: {len(data)} bytes")
    # The stream is a sequence of frames: u16 length, u16 opcode, payload.
    offset = 0
    frames = 0
    item_ids: list[int] = []
    while offset + 4 <= len(data):
        length = struct.unpack_from("<H", data, offset)[0]
        opcode = struct.unpack_from("<H", data, offset + 2)[0]
        if length < 4 or offset + length > len(data):
            print(f"  stop: frame at {offset} length={length} opcode={opcode}")
            break
        payload = data[offset + 4 : offset + length]
        frames += 1
        if frames <= 3:
            print(
                f"  frame {frames}: len={length} opcode={opcode} "
                f"payload[:32]={payload[:32].hex(' ')}"
            )
        # Every 4-byte word in the payload that looks like a plausible item id.
        for i in range(0, len(payload) - 3, 4):
            value = struct.unpack_from("<I", payload, i)[0]
            if 1 <= value <= 20000:
                item_ids.append(value)
        offset += length
    print(f"  frames={frames}")
    unique = sorted(set(item_ids))
    print(f"  candidate ids ({len(unique)}): {unique[:120]}")


def main() -> int:
    for name, data in load_blobs().items():
        walk(data, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
