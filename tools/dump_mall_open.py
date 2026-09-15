"""Raw hex of the mall npc's dialog-open frame (S2C 10067, npc 5212)."""
import subprocess

SQL = ("SELECT captured_at, encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10067 AND direction = 'S2C' "
       "AND captured_at >= '2026-09-13 22:09:43' "
       "AND captured_at <= '2026-09-13 22:09:44' ORDER BY captured_at;")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        when, hexed = parts
        data = bytes.fromhex(hexed)
        print(f"// {when[:23]} len={len(data)}")
        print(f'    "{hexed}"')
        payload = data[4:]
        print("    ascii:",
              "".join(chr(b) if 32 <= b < 127 else "."
                      for b in payload))
        for offset in range(0, 48, 4):
            value = int.from_bytes(payload[offset:offset + 4], "little")
            print(f"    +{offset:<3} {value:>12} (0x{value:08X})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
