"""Field-by-field: the reference's own NPC frame vs the frame we synthesise.

The reference capture holds the object frames the original server sent for
Sparta's city NPCs. Ours are rebuilt field by field, so comparing the two for
the same NPC shows exactly which field a synthesised NPC carries differently -
and every NPC on every other map is synthesised.
"""
import struct
import subprocess

SQL = ("SELECT encode(clear_bytes,'hex') FROM packet_transactions "
       "WHERE opcode = 10020;")


def fields(data):
    object_type = struct.unpack_from("<I", data, 4)[0]
    end = data.index(b"\0", 44)
    return {
        "length": struct.unpack_from("<H", data, 0)[0],
        "opcode": struct.unpack_from("<H", data, 2)[0],
        "objectType": object_type,
        "objectId": struct.unpack_from("<I", data, 8)[0],
        "+12": struct.unpack_from("<I", data, 12)[0],
        "+16": struct.unpack_from("<I", data, 16)[0],
        "+20": struct.unpack_from("<I", data, 20)[0],
        "+24": struct.unpack_from("<I", data, 24)[0],
        "x": struct.unpack_from("<f", data, 28)[0],
        "y": struct.unpack_from("<f", data, 32)[0],
        "z": struct.unpack_from("<f", data, 36)[0],
        "facing": struct.unpack_from("<f", data, 40)[0],
        "template": data[44:end].decode("ascii", "replace"),
        "total": len(data),
    }


def main():
    out = subprocess.run(
        ["docker", "exec", "godswar-postgres", "psql", "-U", "godswar",
         "-d", "godswar", "-t", "-A", "-c", SQL],
        capture_output=True, text=True, check=True).stdout
    wanted = ("Sparta_094_Male30", "Sparta_106_MaleSage1",
              "Sparta_057_FemMale16", "Sparta_012_MaleMerchant3")
    seen = {}
    for row in out.splitlines():
        row = row.strip()
        if not row:
            continue
        data = bytes.fromhex(row)
        if len(data) < 108:
            continue
        item = fields(data)
        if item["template"] in wanted and item["template"] not in seen:
            seen[item["template"]] = item
    for template in wanted:
        item = seen.get(template)
        print(f"--- {template}")
        if item is None:
            print("    (not in the capture)")
            continue
        for key, value in item.items():
            if key in ("x", "y", "z", "facing"):
                print(f"    {key:<10} {value:>12.4f}")
            elif key in ("objectType",):
                print(f"    {key:<10} 0x{value:08X} "
                      f"(map {value >> 16}, low 0x{value & 0xFFFF:04X})")
            else:
                print(f"    {key:<10} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
