"""Every wish/mall board the capture holds: window id, script name, and when.

Window ids appear in the 10021 frames at +4 with the board's script name at +12.
Grouping them answers whether two window ids are the same board seen later or two
different boards.
"""
import collections
import struct
import subprocess

SQL = ("SELECT captured_at, encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10021 ORDER BY captured_at;")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    boards = collections.defaultdict(list)
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, hexed = line.split("|")
        payload = bytes.fromhex(hexed)[4:]
        if len(payload) < 40:
            continue
        window = struct.unpack_from("<I", payload, 0)[0]
        script = payload[8:24].split(b"\0")[0].decode("ascii", "replace")
        boards[(window, script)].append(when[:19])
    print(f"{'window':>8}  {'script':<14}{'frames':>7}  first -> last (UTC)")
    for (window, script), times in sorted(boards.items()):
        print(f"{window:>8}  {script:<14}{len(times):>7}  "
              f"{times[0]} -> {times[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
