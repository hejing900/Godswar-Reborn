"""Check that every captured merchant item is actually published as a template.

A shop can advertise an item the runtime item catalog does not publish; the
reference capture showed those buys being rejected while the client still drew
the slot (docs/shop-purchase-unavailable-20260924.md). This lists the captured
stock against the published item batch so the gap is known before shipping.

Usage: python tools/check_shop_items_published.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import subprocess
import sys

CATALOGS = pathlib.Path(
    r"D:\Godswar-Reborn-main\artifacts\npc-port\shop-catalogs.json")


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    catalogs = json.loads(CATALOGS.read_text(encoding="utf-8"))

    revision = None
    rows = psql("SELECT revision FROM item_template_content_publication LIMIT 1;")
    if rows:
        revision = rows[0].strip()
    print(f"published item revision: {revision}")

    published = set()
    if revision:
        for line in psql("SELECT id FROM item_templates;"):
            published.add(int(line))
    print(f"item_templates rows: {len(published)}")

    stock: dict[int, set[int]] = {}
    for npc, entry in sorted(catalogs.items(), key=lambda kv: int(kv[0])):
        import base64
        import gzip
        import struct
        blob = gzip.decompress(base64.b64decode(entry["gzipBase64"]))
        ids = set()
        offset = 0
        while offset + 16 <= len(blob):
            length = struct.unpack_from("<H", blob, offset)[0]
            body = blob[offset + 16: offset + length]
            cursor = 0
            while cursor + 8 <= len(body):
                ids.add(struct.unpack_from("<I", body, cursor)[0])
                cursor += 88
            offset += length
        stock[int(npc)] = ids

    all_ids = set().union(*stock.values()) if stock else set()
    missing = sorted(all_ids - published)
    print(f"\ndistinct items on the {len(stock)} captured shelves: {len(all_ids)}")
    print(f"missing from item_templates: {len(missing)}")

    # Which shops are affected, and what does the client's own catalogue say?
    affect = collections.Counter()
    for npc, ids in stock.items():
        hit = ids & set(missing)
        if hit:
            affect[npc] = len(hit)
    print(f"\nshops with at least one unpublishable item: {len(affect)}")
    for npc, count in sorted(affect.items()):
        print(f"    npc {npc:>5}: {count:>3} of {len(stock[npc]):>3} items")
    if missing:
        print(f"\nthe missing ids:\n    {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
