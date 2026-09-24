"""Check whether a shop's repeated category frames are paging or duplication.

A merchant frame carries a "fresh list" byte at +11. A paginated category sends
its first page with fresh=1 and continuations with fresh=0; a duplicated frame
would repeat both the flag and the records. This prints both so the catalog
generator can decide whether to concatenate or drop.

Usage: python tools/inspect_shop_frames.py --session <uuid> [--npc 5166]
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import subprocess
import sys

SHOP_HEADER = 16
RECORD = 88


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--npc", type=int)
    args = parser.parse_args()

    sql = ("SELECT id, encode(clear_bytes,'hex') FROM packet_transactions "
           "WHERE opcode=10071 AND direction='S2C' "
           f"AND capture_session_id='{args.session}' ORDER BY id;")
    seen: dict[int, dict[int, list]] = {}
    for line in psql(sql):
        row_id, hexed = line.split("|", 1)
        data = bytes.fromhex(hexed)
        npc_id = struct.unpack_from("<I", data, 4)[0]
        if args.npc and npc_id != args.npc:
            continue
        category = data[8]
        length = struct.unpack_from("<H", data, 0)[0]
        body = data[SHOP_HEADER:length]
        items = []
        offset = 0
        while offset + 8 <= len(body):
            items.append((
                struct.unpack_from("<I", body, offset)[0],
                struct.unpack_from("<I", body, offset + 68)[0]
                if offset + 72 <= len(body) else None,
            ))
            offset += RECORD
        seen.setdefault(npc_id, {}).setdefault(category, []).append({
            "rowId": int(row_id),
            "length": length,
            "currency": data[9],
            "declared": data[10],
            "fresh": data[11],
            "balance": struct.unpack_from("<i", data, 12)[0],
            "records": len(items),
            "items": items,
            "recordHash": hashlib.sha256(
                body[:len(items) * RECORD]).hexdigest()[:12],
        })

    for npc_id in sorted(seen):
        print(f"\n===== npc {npc_id} =====")
        for category in sorted(seen[npc_id]):
            group = seen[npc_id][category]
            print(f"  category {category}: {len(group)} frame(s)")
            for frame in group:
                print(f"    row={frame['rowId']:<7} len={frame['length']:<6} "
                      f"cur=0x{frame['currency']:x} declared={frame['declared']:<3} "
                      f"fresh={frame['fresh']} balance={frame['balance']:<8} "
                      f"records={frame['records']:<3} hash={frame['recordHash']}")
            if len(group) > 1:
                distinct = {f["recordHash"] for f in group}
                ids = [tuple(i[0] for i in f["items"]) for f in group]
                overlap = set(ids[0]) & set(ids[1]) if len(ids) > 1 else set()
                print(f"    -> distinct payloads: {len(distinct)}  "
                      f"item-id overlap frame0&1: {len(overlap)}")
                print(f"       frame0 ids: {ids[0]}")
                if len(ids) > 1:
                    print(f"       frame1 ids: {ids[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
