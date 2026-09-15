"""Detail of the wish frames: the request, its answer and the window slots."""
import struct
import subprocess

SQL = ("SELECT captured_at, direction, opcode, declared_length, "
       "encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE captured_at > '2026-09-13 22:21:00' "
       "AND opcode IN (10021, 10279, 10280, 10038, 10125, 10191) "
       "ORDER BY captured_at;")


def dump(label, payload):
    print(f"  {label}: {len(payload)} payload bytes")
    for offset in range(0, min(len(payload), 176), 32):
        chunk = payload[offset:offset + 32]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        u32 = " ".join(
            f"{struct.unpack_from('<I', chunk, o)[0]:>10}"
            for o in range(0, min(len(chunk), 32), 4))
        print(f"    +{offset:<4} {chunk.hex():<64} |{text}|")
        print(f"          u32: {u32}")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    seen = set()
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 5 or not parts[2].strip():
            continue
        when, direction, opcode, length, hexed = parts
        key = (direction, opcode, length)
        if opcode in ("10021", "10038") and key in seen:
            continue
        seen.add(key)
        data = bytes.fromhex(hexed)
        print(f"=== {when[:23]} {direction} op={opcode} len={length}")
        dump("payload", data[4:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
