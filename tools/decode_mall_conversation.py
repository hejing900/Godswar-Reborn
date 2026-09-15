"""Every frame of the mall conversation with npc 5212, in order."""
import struct
import subprocess

SQL = ("SELECT captured_at, direction, opcode, declared_length, "
       "encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE captured_at >= '2026-09-13 22:09:38' "
       "AND captured_at <= '2026-09-13 22:10:10' "
       "ORDER BY captured_at;")

QUIET = {10015, 10194, 10016, 10017, 10020, 10024, 10312}


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 5:
            continue
        when, direction, opcode, length, hexed = parts
        opcode = int(opcode)
        if opcode in QUIET:
            continue
        data = bytes.fromhex(hexed)
        payload = data[4:]
        words = [struct.unpack_from("<i", payload, off)[0]
                 for off in range(0, min(len(payload), 40), 4)]
        print(f"{when[:23]} {direction:<3} {opcode:>5} len={length:>5} "
              f"words={words}")
        if opcode == 10021:
            print(f"    ascii: "
                  f"{''.join(chr(b) if 32 <= b < 127 else '.' for b in payload[:110])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
