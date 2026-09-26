"""Dump every Address.ini the client ships.

AddressConfig.ini maps an address id to a scene, and each scene's Address.ini
holds `AddressNameN` / `CoordinateN` pairs under `[AddressConfigN]` blocks whose
index is the map id. These are the client's named landing points, which is what
a teleport scroll's ScriptID ultimately has to resolve to.
"""
import os
import re
import json

ROOT = r'D:\Godswar Origin\Localization\en_us'
CLIENT_ROOT = r'D:\Godswar Origin'
CONFIG = os.path.join(ROOT, r'Settings\Sys\AddressConfig.ini')
OUT = r'artifacts\npc-port\client-address-points.json'


def read_lines(path):
    """Decode a client ini and hand back clean, stripped lines.

    The client mixes encodings: AddressConfig.ini is plain UTF-8 while each
    scene's Address.ini carries a UTF-16LE BOM. Detect per file.
    """
    raw = open(path, 'rb').read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = raw.decode('utf-16', 'replace')
    else:
        text = raw.decode('utf-8-sig', 'replace')
    return [line.strip() for line in text.replace('\r', '\n').split('\n')]


def parse_config():
    """address index -> address file, plus map id -> scene name."""
    lines = read_lines(CONFIG)
    by_index, by_id = {}, {}
    for line in lines:
        m = re.fullmatch(r'Address(\d+)=(.*)', line)
        if m:
            by_index[int(m.group(1))] = m.group(2).strip()
    current = None
    for line in lines:
        m = re.fullmatch(r'\[AddressConfig(\d+)\]', line)
        if m:
            current = int(m.group(1))
            continue
        m = re.fullmatch(r'name=(.*)', line)
        if m and current is not None:
            by_id[current] = m.group(1).strip()
    return by_index, by_id


def parse_address(path):
    """map id -> [(name, x, z)] for every [N] block in one Address.ini."""
    if not os.path.exists(path):
        return {}
    lines = read_lines(path)
    blocks, cur, rows = {}, None, []
    for line in lines:
        m = re.fullmatch(r'\[(\d+)\].*', line)
        if m:
            if cur is not None:
                blocks[cur] = rows
            cur, rows = int(m.group(1)), []
            continue
        if cur is None:
            continue
        m = re.match(r'AddressName(\d+)\s*=\s*(.*?);?$', line)
        if m:
            rows.append([int(m.group(1)), m.group(2).strip(), None])
            continue
        m = re.match(r'Coordinate(\d+)\s*=\s*([-\d.]+)\s*,\s*([-\d.]+)', line)
        if m:
            idx = int(m.group(1))
            for row in rows:
                if row[0] == idx:
                    row[2] = (float(m.group(2)), float(m.group(3)))
                    break
    if cur is not None:
        blocks[cur] = rows
    return blocks


by_index, by_id = parse_config()
print(f'address files listed   : {len(by_index)}')
print(f'AddressConfig blocks   : {len(by_id)}')
print()

result = {}
for index, rel in sorted(by_index.items()):
    rel = rel.lstrip('./').replace('/', os.sep)
    path = os.path.join(CLIENT_ROOT, rel)
    blocks = parse_address(path)
    if not blocks:
        print(f'  MISSING/EMPTY index={index} {rel}')
        continue
    for map_id, rows in blocks.items():
        scene = by_id.get(map_id, f'<unnamed {map_id}>')
        points = [
            dict(name=r[1], x=r[2][0], z=r[2][1])
            for r in rows if r[2] is not None
        ]
        result.setdefault(str(map_id), dict(
            map_id=map_id, scene=scene, address_index=index, points=[]))
        result[str(map_id)]['points'].extend(points)

total = sum(len(v['points']) for v in result.values())
print(f'maps with address points: {len(result)}')
print(f'total address points    : {total}')
print()
print(f'{"map":>4} {"scene":<34} {"points":>7}')
print('-' * 50)
for key in sorted(result, key=lambda k: int(k)):
    v = result[key]
    print(f'{v["map_id"]:>4} {v["scene"]:<34} {len(v["points"]):>7}')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)
print()
print(f'wrote {OUT}')
