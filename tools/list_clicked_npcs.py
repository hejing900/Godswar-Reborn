"""Every npc the client ever clicked in the capture, with its local time."""
import struct
import subprocess

SQL = ("SELECT captured_at AT TIME ZONE 'Asia/Shanghai', "
       "encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10067 AND direction = 'C2S' ORDER BY captured_at;")


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-F", "|", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        when, hexed = line.split("|")
        data = bytes.fromhex(hexed)
        npc = struct.unpack_from("<I", data, 4)[0]
        rows.append((when[:19], npc))
    print(f"client npc clicks in the capture: {len(rows)}")
    counted = {}
    for when, npc in rows:
        counted.setdefault(npc, []).append(when)
    for npc in sorted(counted):
        times = counted[npc]
        print(f"  npc {npc:<7} clicks={len(times):<3} "
              f"{times[0]} -> {times[-1]}")
    print()
    print("in order:")
    for when, npc in rows:
        print(f"  {when}  npc={npc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
