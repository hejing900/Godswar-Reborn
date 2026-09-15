"""Decode the client's own movement report and compare npc appearance flags."""
import struct
import subprocess

# op=10194 payload: 4 bytes header, then X, Z, Y as little-endian floats.
SAMPLES = {
    "click on Acacia": "C4772243B100A7C2946D9540",
    "latest (at the guide)": "A7282143145EB9C2D6408940",
}

SQL = ("SELECT npc_key, object_id, appearance_type, map_id "
       "FROM npc_spawn_definitions WHERE npc_key IN "
       "('Sparta_094','Sparta_106','Sparta_057','Sparta_Newbie_005',"
       "'Athens_094','Athens_106','Athens_095','Athens_099') "
       "ORDER BY map_id, npc_key;")


def main():
    for label, hexed in SAMPLES.items():
        x, z, y = struct.unpack_from("<fff", bytes.fromhex(hexed), 0)
        print(f"{label}: x={x:.2f} z={z:.2f} y={y:.2f}")
    print()
    print(subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-c", SQL],
        capture_output=True, text=True, check=True).stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
