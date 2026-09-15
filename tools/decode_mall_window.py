"""Look at the mall's window frame (S2C 10021) the reference sent."""
import subprocess

SQL = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10021 ORDER BY captured_at DESC LIMIT 1;")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", SQL],
        capture_output=True, text=True, check=True).stdout.strip()
    data = bytes.fromhex(out)
    payload = data[4:]
    print(f"frame {len(data)} bytes, payload {len(payload)}")
    print("ascii:", "".join(chr(b) if 32 <= b < 127 else "." for b in payload))
    print()
    for offset in range(0, len(payload), 32):
        print(f"+{offset:<4} {payload[offset:offset + 32].hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
