"""Prove which server a capture session talked to.

Our server could not have produced the captured 10076 for quest 532: its builder
writes kind 8 when the quest has a kill objective, and the captured frame carries
kind 4. This also reads the 10020 spawn frames of the same session and reports
which map they place monsters on, which is the other half of the argument - the
client was seeing map-4 monsters hours before our server had any.
"""
import struct
import subprocess

WINDOW = ("captured_at >= '2026-09-13 00:57:00' AND "
          "captured_at <= '2026-09-13 00:59:59'")


def query(sql):
    return subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, check=True).stdout


def main():
    rows = query(
        "SELECT encode(clear_bytes,'hex') FROM packet_transactions "
        f"WHERE opcode = 10020 AND {WINDOW};")
    maps = {}
    for row in rows.splitlines():
        row = row.strip()
        if not row:
            continue
        data = bytes.fromhex(row)
        if len(data) < 108:
            continue
        object_type = struct.unpack_from("<I", data, 4)[0]
        map_id = (object_type >> 16) & 0xFFFF
        name_end = data.index(b"\0", 44)
        template = data[44:name_end].decode("ascii", "replace")
        maps.setdefault(map_id, set()).add(template)
    print("10020 spawn frames in the session, by placed map:")
    for map_id, templates in sorted(maps.items()):
        print(f"  map {map_id}: {len(templates)} template(s)")
        if map_id == 4:
            for template in sorted(templates):
                print(f"      {template}")

    hand_in = query(
        "SELECT captured_at, opcode, encode(clear_bytes,'hex') "
        "FROM packet_transactions "
        f"WHERE opcode IN (10086, 10076, 10082, 10087) AND {WINDOW} "
        "ORDER BY captured_at;")
    print()
    print("quest frames in the same session:")
    for row in hand_in.splitlines():
        when, opcode, hexed = row.split("|")
        data = bytes.fromhex(hexed)
        if opcode == "10086":
            detail = f"giver={struct.unpack_from('<I', data, 4)[0]} quest={struct.unpack_from('<I', data, 12)[0]}"
        elif opcode == "10076":
            detail = (f"giver={struct.unpack_from('<I', data, 4)[0]} "
                      f"quest={struct.unpack_from('<I', data, 8)[0]} "
                      f"kind={struct.unpack_from('<i', data, 16)[0]} "
                      f"monster={struct.unpack_from('<I', data, 28)[0]}")
        else:
            detail = f"quest={struct.unpack_from('<I', data, 12)[0]}"
        print(f"  {when} {opcode} {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
