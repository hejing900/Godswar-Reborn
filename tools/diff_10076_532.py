"""Byte-diff our 10076 for quest 532 against the reference server's own frame.

Our frame is read back from the server's own frame trace, the reference's from
the captured traffic, so neither side is transcribed by hand.
"""
import re
import struct
import subprocess

TRACE = "grep 'QuestNextDetail' /tmp/quest-frames.log | tail -1"
SQL = ("SELECT encode(clear_bytes, 'hex') FROM packet_transactions "
       "WHERE opcode = 10076 "
       "AND encode(clear_bytes, 'hex') LIKE '64015c2753fc000014020000%' "
       "LIMIT 1;")


def shell(args):
    return subprocess.run(args, capture_output=True, text=True,
                          check=True).stdout


def ours():
    line = shell(["docker", "exec", "godswar-server", "sh", "-c", TRACE])
    blob = re.search(r"hex=([0-9a-fA-F]+)", line).group(1)
    return bytes.fromhex(blob)


def theirs():
    out = shell(["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
                 "-d", "godswar", "-t", "-A", "-c", SQL]).strip()
    if out.startswith("\\x"):
        out = out[2:]
    return bytes.fromhex(out)


def main():
    mine = ours()
    reference = theirs()
    print(f"ours {len(mine)} bytes, reference {len(reference)} bytes")
    print(f"declared length ours={struct.unpack_from('<H', mine, 0)[0]} "
          f"reference={struct.unpack_from('<H', reference, 0)[0]}")
    print(f"quest ours={struct.unpack_from('<I', mine, 8)[0]} "
          f"reference={struct.unpack_from('<I', reference, 8)[0]}")
    print(f"kind ours={struct.unpack_from('<i', mine, 16)[0]} "
          f"reference={struct.unpack_from('<i', reference, 16)[0]}")
    print(f"monster ours={struct.unpack_from('<I', mine, 28)[0]} "
          f"reference={struct.unpack_from('<I', reference, 28)[0]}")
    print(f"need ours={struct.unpack_from('<i', mine, 44)[0]} "
          f"reference={struct.unpack_from('<i', reference, 44)[0]}")
    differences = [index for index in range(min(len(mine), len(reference)))
                   if mine[index] != reference[index]]
    print(f"differing bytes: {len(differences)}")
    for offset in differences[:40]:
        print(f"  +{offset:<4} ours={mine[offset]:02X} "
              f"reference={reference[offset]:02X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
