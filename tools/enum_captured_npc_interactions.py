"""Build the per-NPC interaction inventory the capture holds.

Three opcodes carry the NPC interaction surface, all keyed by the *runtime*
npc id the client was given (the same ids the 10071 shop frames use):

* 10077 S2C - the clickable-dialogue list: u32 count then count*(u32 dialogId, u32 reserved)
* 10080 S2C - the clickable-action list: count then count*u32 dialogId
* 10071 S2C - merchant stock (category/currency/records)

Combined with the 10020 placements (objectId -> template) this says, for every
placed NPC, whether the reference server gave it a dialogue menu and/or a shop.

Usage: python tools/enum_captured_npc_interactions.py [out.json]
"""
from __future__ import annotations

import collections
import json
import os
import struct
import subprocess
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Godswar-Reborn-main\artifacts\npc-port\captured-npc-interactions.json"


def rows(sql: str) -> list[str]:
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def load_placements() -> dict[int, str]:
    """runtime npc id -> appearance template, from the 10020 placements."""
    mapping: dict[int, str] = {}
    import pathlib
    for path in pathlib.Path(r"D:\Godswar-Reborn-main\artifacts\npc-port") \
            .glob("captured-npcs-map*.txt"):
        for line in open(path, encoding="utf-8"):
            if line.startswith("#"):
                continue
            parts = line.strip().split("|")
            if len(parts) == 6:
                mapping[int(parts[0])] = parts[1]
    return mapping


def decode_10077(data: bytes):
    if len(data) < 8:
        return None
    npc_id, count = struct.unpack_from("<II", data, 4)
    options = []
    for index in range(count):
        off = 12 + index * 8
        if off + 8 > len(data):
            break
        dialog_id, reserved = struct.unpack_from("<II", data, off)
        options.append({"dialogId": dialog_id, "reserved": reserved})
    return npc_id, count, options


def decode_10080(data: bytes):
    if len(data) < 8:
        return None
    npc_id, count = struct.unpack_from("<II", data, 4)
    options = []
    for index in range(count):
        off = 12 + index * 4
        if off + 4 > len(data):
            break
        options.append(struct.unpack_from("<I", data, off)[0])
    return npc_id, count, options


def decode_10071(data: bytes):
    if len(data) < 16:
        return None
    npc_id = struct.unpack_from("<I", data, 4)[0]
    return (npc_id, data[8], data[9], data[10],
            struct.unpack_from("<i", data, 12)[0])


def main() -> int:
    placements = load_placements()
    dialogues: dict[int, list] = collections.defaultdict(list)
    actions: dict[int, list] = collections.defaultdict(list)
    shops: dict[int, set] = collections.defaultdict(set)

    for line in rows("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
                     "WHERE opcode=10077 AND direction='S2C' ORDER BY id;"):
        decoded = decode_10077(bytes.fromhex(line))
        if decoded:
            npc_id, _, options = decoded
            dialogues[npc_id].append([o["dialogId"] for o in options])
    for line in rows("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
                     "WHERE opcode=10080 AND direction='S2C' ORDER BY id;"):
        decoded = decode_10080(bytes.fromhex(line))
        if decoded:
            npc_id, _, options = decoded
            actions[npc_id].append(options)
    for line in rows("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
                     "WHERE opcode=10071 AND direction='S2C' ORDER BY id;"):
        decoded = decode_10071(bytes.fromhex(line))
        if decoded:
            shops[decoded[0]].add(decoded[1])

    every = sorted(set(placements) | set(dialogues) | set(actions) | set(shops))
    report = {}
    for npc_id in every:
        report[npc_id] = {
            "template": placements.get(npc_id, ""),
            "dialogueFrames": dialogues.get(npc_id, []),
            "actionFrames": actions.get(npc_id, []),
            "shopCategories": sorted(shops.get(npc_id, ())),
        }

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump({str(k): v for k, v in report.items()}, handle, indent=2,
                  ensure_ascii=False)

    interactive = {k: v for k, v in report.items()
                   if v["dialogueFrames"] or v["actionFrames"] or v["shopCategories"]}
    print(f"placed npcs: {len(placements)}")
    print(f"npcs with a dialogue menu (10077): {len(dialogues)}")
    print(f"npcs with an action menu  (10080): {len(actions)}")
    print(f"npcs with a shop          (10071): {len(shops)}")
    print(f"npcs with any interaction surface: {len(interactive)}")
    print(f"\nwrote {OUT}\n")
    print(f"{'id':>6}  {'template':<44} {'dlg':>4} {'act':>4} {'shop':>4}")
    for npc_id in sorted(interactive):
        entry = interactive[npc_id]
        print(f"{npc_id:>6}  {entry['template']:<44} "
              f"{len(entry['dialogueFrames']):>4} {len(entry['actionFrames']):>4} "
              f"{len(entry['shopCategories']):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
