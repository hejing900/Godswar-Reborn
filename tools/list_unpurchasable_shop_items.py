"""List every shop listing whose item is absent from the published item catalog.

Any such listing is visible in the vendor window but cannot be bought: the
purchase path has to materialise the item from its template.

Usage: python tools/list_unpurchasable_shop_items.py
"""
from __future__ import annotations

import base64
import gzip
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(r"D:\Godswar-Reborn-main")
MALL = ROOT / "src/Godswar.Server/Packets/PacketBuilder.MallCatalog.cs"
CAPTURED = ROOT / "src/Godswar.Server/Packets/PacketBuilder.CapturedCapitalNpcShops.cs"


def published_ids() -> set[int]:
    sql = (
        "select id from item_template_content_definitions where revision = "
        "(select revision from item_template_content_publication "
        "where family='items');"
    )
    out = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "godswar-postgres",
            "psql",
            "-U",
            "godswar",
            "-d",
            "godswar_local",
            "-t",
            "-A",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return {int(line) for line in out.stdout.split() if line.strip().isdigit()}


def mall_listings() -> list[tuple[int, int, int]]:
    text = MALL.read_text(encoding="utf-8")
    rows: list[tuple[int, int, int]] = []
    for name, blob in re.findall(
        r"private const string (\w+Gzip) =(.*?);", text, re.S
    ):
        b64 = "".join(re.findall(r'"([A-Za-z0-9+/=]*)"', blob))
        data = gzip.decompress(base64.b64decode(b64))
        offset = 0
        frame = 0
        while offset + 8 <= len(data):
            length = struct.unpack_from("<H", data, offset)[0]
            frame += 1
            count = (length - 8) // 88
            for index in range(count):
                ro = offset + 8 + index * 88
                item_id = struct.unpack_from("<I", data, ro)[0]
                price = struct.unpack_from("<I", data, ro + 68)[0]
                rows.append((item_id, price, frame))
            offset += length
    return rows


def main() -> int:
    published = published_ids()
    print(f"published item catalog holds {len(published)} items")
    seen: dict[int, tuple[int, int]] = {}
    for item_id, price, frame in mall_listings():
        seen.setdefault(item_id, (price, frame))
    missing = sorted(
        (item_id, price, frame)
        for item_id, (price, frame) in seen.items()
        if item_id not in published
    )
    print(f"\nmall listings whose item is NOT published: {len(missing)}")
    print(f"{'itemId':>8} {'price':>8} {'frame':>6}")
    for item_id, price, frame in missing:
        print(f"{item_id:>8} {price:>8} {frame:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
