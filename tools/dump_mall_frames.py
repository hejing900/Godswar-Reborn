"""Raw hex of every frame the mall window opened with (window id 765)."""
import subprocess

SQL = ("SELECT captured_at, direction, opcode, declared_length, "
       "encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE captured_at >= '2026-09-13 22:09:50.20' "
       "AND captured_at <= '2026-09-13 22:09:50.30' "
       "AND opcode IN (10067, 10021, 10201, 10248, 10199) "
       "ORDER BY captured_at;")

WANT = (10067, 10021, 10201, 10248, 10199)


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 5 or not parts[2].strip():
            continue
        when, direction, opcode, length, hexed = parts
        if int(opcode) not in WANT:
            continue
        print(f"// {when[:23]} {direction} op={opcode} len={length}")
        for offset in range(0, len(hexed), 64):
            print(f'    "{hexed[offset:offset + 64]}" +')
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
