"""List every map transition the capture holds, with its landing coordinate.

10018 is the reference server's landing frame: +4 object id, +8 f32 X, +16 f32 Z,
+20 map id (low 16 bits). Each one is a real landing, so the set of them is the
authoritative table of where this server puts a character after a teleport.
"""
import json
import struct
import subprocess
import sys

DB = 'godswar'
POINTS = r'artifacts\npc-port\client-address-points.json'


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


rows = query("""
    SELECT id, captured_at, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode = 10018 AND direction = 'S2C'
    ORDER BY id;
""")

landings = []
for line in rows:
    parts = line.split('|', 2)
    if len(parts) != 3:
        continue
    row_id, at, blob = parts
    data = bytes.fromhex(blob)
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        frame = data[off:off + length]
        if op == 10018 and len(frame) >= 28:
            obj, = struct.unpack_from('<I', frame, 4)
            x, = struct.unpack_from('<f', frame, 8)
            z, = struct.unpack_from('<f', frame, 16)
            mid, = struct.unpack_from('<H', frame, 20)
            landings.append((int(row_id), at, obj, mid, x, z))
        off += length

print(f'landing frames: {len(landings)}')

# The client's named address points, for comparison.
client = json.load(open(POINTS, encoding='utf-8'))
by_map = {int(k): v for k, v in client.items()}


def nearest(map_id, x, z):
    entry = by_map.get(map_id)
    if not entry:
        return None, None
    best, bestd = None, None
    for p in entry['points']:
        d = ((p['x'] - x) ** 2 + (p['z'] - z) ** 2) ** 0.5
        if bestd is None or d < bestd:
            best, bestd = p, d
    return best, bestd


print()
print(f'{"id":>7} {"obj":>5} {"map":>4} {"x":>9} {"z":>9}   '
      f'{"nearest client address point":<34} {"dist":>7}')
print('-' * 96)
seen = set()
for row_id, at, obj, mid, x, z in landings:
    key = (mid, round(x, 1), round(z, 1))
    p, d = nearest(mid, x, z)
    label = f'{p["name"]} ({p["x"]},{p["z"]})' if p else '-'
    dist = '-' if d is None else round(d, 1)
    dup = '' if key not in seen else '  (repeat)'
    seen.add(key)
    print(f'{row_id:>7} {obj:>5} {mid:>4} {x:>9.1f} {z:>9.1f}   '
          f'{label:<34} {dist:>7}{dup}')

print()
print('=== distinct landings ===')
distinct = sorted({(mid, round(x, 1), round(z, 1)) for _, _, _, mid, x, z in landings})
print(f'{len(distinct)} distinct (map, x, z)')
for mid, x, z in distinct:
    p, d = nearest(mid, x, z)
    entry = by_map.get(mid)
    scene = entry['scene'] if entry else '?'
    label = f'{p["name"]}' if p else '-'
    print(f'  map {mid:>3} ({scene:<22}) x={x:<9} z={z:<9} '
          f'near {label:<22} dist={d if d is None else round(d, 1)}')
