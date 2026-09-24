"""Turn the latest capture session's merchant stock into server catalog blobs.

The server ships each NPC shop as one gzip+base64 constant holding the exact
opcode-10071 frame stream the reference server sent; only the NPC id and the
live balance are patched at egress. This tool rebuilds those blobs from
``packet_transactions`` so a newly captured shop can be added without hand
assembly.

Frame layout (authoritative, see docs/point-exchanger-shop.md):
  header 16 bytes: +0 u16 length, +2 u16 opcode=10071, +4 u32 npcId,
                   +8 u8 category, +9 u8 currency, +10 u8 count,
                   +11 u8 fresh, +12 i32 balance
  record 88 bytes: +0 u32 itemId, +68 u32 unitPrice, +84 u32 quantity
The last record of a frame is often 4 bytes short; it is zero-padded back to
the 88-byte step because the client addresses records at a fixed stride.

Usage:
  python tools/gen_captured_shop_catalogs.py --session <uuid> [--out FILE]
"""
from __future__ import annotations

import argparse
import base64
import collections
import gzip
import io
import json
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


def load_frames(session: str, start: str | None = None,
                end: str | None = None) -> list[tuple[int, bytes]]:
    where = (f"opcode=10071 AND direction='S2C' "
             f"AND capture_session_id='{session}'")
    # Windows are given in local time; the table stores UTC.
    if start:
        where += (f" AND captured_at + interval '8 hours' >= "
                  f"timestamp '{start}'")
    if end:
        where += (f" AND captured_at + interval '8 hours' < "
                  f"timestamp '{end}'")
    sql = ("SELECT id, encode(clear_bytes,'hex') FROM packet_transactions "
           f"WHERE {where} ORDER BY id;")
    return [(int(part[0]), bytes.fromhex(part[1]))
            for part in (line.split("|", 1) for line in psql(sql))]


def pad_frame(data: bytes) -> bytes:
    """Zero-extend a short trailing record back to the 88-byte stride."""
    length = struct.unpack_from("<H", data, 0)[0]
    body = bytearray(data[:length])
    remainder = (len(body) - SHOP_HEADER) % RECORD
    if remainder:
        body.extend(b"\0" * (RECORD - remainder))
        struct.pack_into("<H", body, 0, len(body))
    return bytes(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True,
                        help="capture_session_id to harvest")
    parser.add_argument("--out", default="artifacts/npc-port/shop-catalogs.json")
    parser.add_argument("--cs", help="also emit a C# fragment")
    parser.add_argument("--from", dest="start",
                        help="local-time lower bound, e.g. "
                             "'2026-09-24 23:48:00'")
    parser.add_argument("--to", dest="end",
                        help="local-time exclusive upper bound")
    args = parser.parse_args()

    frames = load_frames(args.session, args.start, args.end)
    if not frames:
        print(f"session {args.session} holds no 10071 frames "
              f"in the requested window")
        return 1

    by_npc: dict[int, list[bytes]] = collections.defaultdict(list)
    meta: dict[int, list[dict]] = collections.defaultdict(list)
    for _, data in frames:
        if len(data) < SHOP_HEADER:
            continue
        npc_id = struct.unpack_from("<I", data, 4)[0]
        category = data[8]
        declared = data[10]
        body = data[SHOP_HEADER:]
        records = 0
        offset = 0
        while offset + 8 <= len(body):
            records += 1
            offset += RECORD
        by_npc[npc_id].append(pad_frame(data))
        meta[npc_id].append({"category": category,
                             "currency": data[9],
                             "declared": declared,
                             "records": records})

    print(f"session {args.session}: {len(frames)} frames, "
          f"{len(by_npc)} shop npcs")

    result = {}
    for npc_id in sorted(by_npc):
        stream = b"".join(by_npc[npc_id])
        compressed = gzip.compress(stream, 9, mtime=0)
        entry = {
            "npcId": npc_id,
            "frameCount": len(by_npc[npc_id]),
            "totalBytes": len(stream),
            "itemCount": sum(m["records"] for m in meta[npc_id]),
            "frames": meta[npc_id],
            "gzipBase64": base64.b64encode(compressed).decode("ascii"),
        }
        result[str(npc_id)] = entry
        print(f"  npc {npc_id:>5}: {entry['frameCount']} frames "
              f"{entry['totalBytes']:>6} bytes {entry['itemCount']:>3} items "
              f"cats={[m['category'] for m in meta[npc_id]]} "
              f"cur={[hex(m['currency']) for m in meta[npc_id]]}")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
