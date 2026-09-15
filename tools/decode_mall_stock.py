"""Decode the mall's stock frames (S2C 10021 header, 10022 items)."""
import struct
import subprocess

SQL = ("SELECT captured_at, opcode, declared_length, "
       "encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE captured_at > '2026-09-13 22:06:30' "
       "AND opcode IN (10021, 10022) ORDER BY captured_at;")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            continue
        when, opcode, length, hexed = parts
        data = bytes.fromhex(hexed)
        payload = data[4:]
        print(f"=== {when[:23]} op={opcode} len={length}")
        words = [struct.unpack_from("<I", payload, off)[0]
                 for off in range(0, min(len(payload), 64), 4)]
        print("    first words:", words)
        shorts = [struct.unpack_from("<H", payload, off)[0]
                  for off in range(0, min(len(payload), 32), 2)]
        print("    first shorts:", shorts)
        for offset in range(0, min(len(payload), 128), 32):
            print(f"    +{offset:<4} {payload[offset:offset + 32].hex()}")
        body = len(payload)
        for record in (4, 8, 12, 16, 20, 24, 28, 32, 36):
            if body % record == 0:
                print(f"    {body} payload bytes = {body // record} "
                      f"records of {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
