"""Decode the mall interaction from the newest capture window.

The shop sequence is: press the npc (C2S 10067) -> dialog (S2C 10067) -> pick a
function (C2S 10069) -> the server answers the menu (S2C 10070) and the stock
(S2C 10021 / 10022). This prints each frame of that sequence with its header
words, so the dialog index, sub id and list sizes the reference used are visible.
"""
import struct
import subprocess

WINDOW = "captured_at > '2026-09-13 22:06:30'"
OPCODES = (10067, 10068, 10069, 10070, 10021, 10022, 10035, 10117, 10297)

SQL = (f"SELECT captured_at, direction, opcode, declared_length, "
       f"encode(clear_bytes,'hex') FROM packet_transactions "
       f"WHERE {WINDOW} AND opcode IN "
       f"({','.join(str(o) for o in OPCODES)}) ORDER BY captured_at;")


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
        data = bytes.fromhex(hexed)
        payload = data[4:]
        words = " ".join(
            f"{struct.unpack_from('<I', payload, off)[0]:>10}"
            for off in range(0, min(len(payload), 32), 4))
        print(f"{when[:23]} {direction:<3} {opcode:>5} len={length:>5}  "
              f"+0..+28: {words}")
        if opcode in (10069, 10070, 10022, 10021) and len(payload) >= 8:
            print(f"    hex: {data[:64].hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
