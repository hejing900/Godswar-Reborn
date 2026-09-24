"""Enumerate every NPC shop catalog the capture stream holds.

Reads opcode 10071 (merchant stock) and the mall family out of
``packet_transactions`` and prints, per NPC id, every distinct category frame
with its currency, item count and itemId:price pairs. The output is the
migration work list: which captured shop a server build is still missing.

Usage:
  python tools/enum_captured_shops.py [--opcode 10071] [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
import subprocess
import sys

PSQL = ["docker", "exec", "godswar-postgres", "psql",
        "-U", "godswar", "-d", "godswar", "-t", "-A", "-c"]

SHOP_HEADER = 16
RECORD = 88

CURRENCY = {0x01: "gold?", 0x02: "gold", 0x03: "silver", 0x04: "boundGold"}


def query(sql: str) -> list[str]:
    out = subprocess.run(PSQL + [sql], capture_output=True, text=True,
                         check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def frames(opcode: int) -> list[tuple[int, int, bytes]]:
    """Yield (id, captured_at_epoch, clear_bytes) for one opcode."""
    sql = ("SELECT id, extract(epoch from captured_at)::bigint, "
           "encode(clear_bytes,'hex') FROM packet_transactions "
           f"WHERE opcode = {opcode} AND direction = 'S2C' ORDER BY id;")
    for line in query(sql):
        parts = line.split("|")
        if len(parts) != 3:
            continue
        yield int(parts[0]), int(parts[1]), bytes.fromhex(parts[2])


def decode_shop_frame(data: bytes) -> dict | None:
    """One 10071 frame: 16-byte header then N x 88-byte records."""
    if len(data) < SHOP_HEADER:
        return None
    length, opcode, npc_id = struct.unpack_from("<HHI", data, 0)
    if opcode != 10071:
        return None
    category = data[8]
    currency = data[9]
    declared = data[10]
    fresh = data[11]
    balance = struct.unpack_from("<i", data, 12)[0]

    body = data[SHOP_HEADER:]
    # The last record of a frame is frequently 4 bytes short; pad to step.
    records = []
    offset = 0
    while offset + 8 <= len(body):
        item_id = struct.unpack_from("<I", body, offset)[0]
        price = struct.unpack_from("<I", body, offset + 68)[0] \
            if offset + 72 <= len(body) else None
        quantity = struct.unpack_from("<I", body, offset + 84)[0] \
            if offset + 88 <= len(body) else None
        records.append({"itemId": item_id, "price": price,
                        "quantity": quantity})
        offset += RECORD
    return {
        "declaredLength": length,
        "actualLength": len(data),
        "npcId": npc_id,
        "category": category,
        "currency": currency,
        "currencyName": CURRENCY.get(currency, f"0x{currency:02x}"),
        "declaredCount": declared,
        "freshList": fresh,
        "balance": balance,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opcode", type=int, default=10071)
    parser.add_argument("--json")
    args = parser.parse_args()

    shops: dict[int, dict[int, dict]] = collections.defaultdict(dict)
    for _, _, data in frames(args.opcode):
        decoded = decode_shop_frame(data)
        if decoded is None:
            continue
        npc = decoded["npcId"]
        key = decoded["category"]
        prior = shops[npc].get(key)
        # Keep the richest observation of each (npc, category) pair.
        if prior is None or len(decoded["records"]) > len(prior["records"]):
            shops[npc][key] = decoded

    if not shops:
        print(f"no shop frames for opcode {args.opcode}")
        return 0

    total = 0
    for npc in sorted(shops):
        categories = shops[npc]
        print(f"\n=== NPC {npc}: {len(categories)} category frame(s)")
        for category in sorted(categories):
            frame = categories[category]
            records = frame["records"]
            total += len(records)
            print(f"  cat {category:>3} currency={frame['currencyName']:<9} "
                  f"count={len(records):>2}/declared {frame['declaredCount']:>2} "
                  f"fresh={frame['freshList']} len={frame['actualLength']}")
            for index, record in enumerate(records):
                print(f"      [{index:>2}] {record['itemId']:>6} : "
                      f"{record['price']}")
    print(f"\ntotal records: {total}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({str(k): {str(c): v for c, v in cats.items()}
                       for k, cats in shops.items()},
                      handle, indent=2, ensure_ascii=False)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
