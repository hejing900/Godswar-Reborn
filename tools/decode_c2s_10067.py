"""Decode C2S 10067 (npc dialog open): what the client sends and what it names.

The request carries the npc id and a script string, so the client only asks for
dialogs it has a script for. Comparing our client's request for an Athens npc
with the reference capture's requests for Sparta npcs shows which names the
client uses and which npcs it stays silent about.
"""
import struct
import subprocess

OURS = ("SELECT captured_at, encode(clear_bytes,'hex') "
        "FROM packet_transactions WHERE opcode = 10067 AND direction = 'C2S' "
        "ORDER BY captured_at LIMIT 12;")


def decode(data):
    npc = struct.unpack_from("<I", data, 0)[0]
    second = struct.unpack_from("<I", data, 4)[0]
    text = data[8:].split(b"\0")[0].decode("ascii", "replace")
    return npc, second, text


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", OURS],
        capture_output=True, text=True, check=True).stdout
    print("reference capture, C2S 10067 (payload after the 4-byte header):")
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, hexed = line.split("|")
        # The captured blob includes the frame header; the payload is at +4.
        data = bytes.fromhex(hexed)[4:]
        npc, second, text = decode(data)
        print(f"  {when[:23]} npc={npc:<6} word={second:<10} text={text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
