"""The wishing pool conversation, in order, with its frames decoded."""
import struct
import subprocess

SQL = ("SELECT captured_at, direction, opcode, declared_length, "
       "encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE captured_at > '2026-09-13 22:20:00' "
       "AND opcode NOT IN (10015, 10194, 10016, 10017, 10020, 10024, 10312, "
       "10023, 10025, 10339, 10077, 10080, 10297, 10309, 10166) "
       "ORDER BY captured_at;")


def words(payload, count):
    return [struct.unpack_from("<i", payload, off)[0]
            for off in range(0, min(len(payload), count * 4), 4)]


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
        data = bytes.fromhex(hexed)
        payload = data[4:]
        print(f"{when[:23]} {direction:<3} {opcode:>5} len={length:>5} "
              f"words={words(payload, 10)}")
        if len(payload) >= 8:
            ascii_text = "".join(
                chr(b) if 32 <= b < 127 else "." for b in payload[:64])
            if any(c.isalpha() for c in ascii_text):
                print(f"      ascii: {ascii_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
