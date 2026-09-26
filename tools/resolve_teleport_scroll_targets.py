"""Match every FlyBook teleport scroll to a landing coordinate.

The chain is: item (FlyBook n) -> Skill -> ScriptID (FlyTo...) -> a named
landing point. The client ships no coordinates for the ScriptID, so the only
coordinate table it has is each scene's Address.ini. This resolves the scroll's
destination name against those landing points and reports which ones line up.
"""
import json
import re
import xml.etree.ElementTree as ET

SYS = r'D:\Godswar Origin\Localization\en_us\Settings\Sys'
ITEMS = SYS + r'\ItemBaseAttribute.xml'
MAGIC = SYS + r'\Magic.ini'
NAMES = r'D:\Godswar Origin\Localization\en_us\Text\EquipName.dat'
POINTS = r'artifacts\npc-port\client-address-points.json'


def read_text(path):
    raw = open(path, 'rb').read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16', 'replace')
    return raw.decode('utf-8-sig', 'replace')


# --- 1. scroll items -----------------------------------------------------
raw_xml = read_text(ITEMS)
scrolls = []
for m in re.finditer(r'<(FlyBook\d+)\s+([^>]*?)/?>', raw_xml):
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
    scrolls.append(dict(
        key=m.group(1),
        item_id=int(attrs['ID']),
        skill=int(attrs['Skill']),
        camp=attrs.get('Camp'),
        level=attrs.get('PlayLv'),
        gold=int(attrs.get('Money', 0)),
    ))
scrolls.sort(key=lambda r: r['item_id'])
print(f'FlyBook scrolls: {len(scrolls)}')

# --- 2. display names ----------------------------------------------------
display = {}
for line in read_text(NAMES).splitlines():
    parts = line.strip().split('\t')
    if len(parts) >= 2:
        display[parts[0].strip()] = parts[1].strip()

# --- 3. skills -----------------------------------------------------------
sections, cur, buf = {}, None, []
for line in read_text(MAGIC).replace('\r', '\n').split('\n'):
    line = line.strip()
    m = re.fullmatch(r'\[(\d+)\]', line)
    if m:
        if cur is not None:
            sections[cur] = buf
        cur, buf = int(m.group(1)), []
        continue
    if cur is not None and '=' in line:
        k, v = line.split('=', 1)
        buf.append((k.strip(), v.strip()))
if cur is not None:
    sections[cur] = buf

# --- 4. landing points ---------------------------------------------------
points = json.load(open(POINTS, encoding='utf-8'))

CAMP = {None: 'any', '0': 'Sparta', '1': 'Athens'}


def norm(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


# Build a lookup: normalised landing name -> (map id, scene, x, z)
by_name = {}
for key, entry in points.items():
    for p in entry['points']:
        by_name.setdefault(norm(p['name']), []).append(
            (entry['map_id'], entry['scene'], p['x'], p['z'], p['name']))

print()
print('=== scroll -> skill -> script -> landing coordinate ===')
print()
for row in scrolls:
    fields = dict(sections.get(row['skill'], []))
    skill_name = fields.get('Name', '<missing>')
    script = fields.get('ScriptID', '<none>')
    cn = display.get(row['key'], '?')

    # Try the scroll's own display name, then the skill name, against the
    # named landing points.
    found = []
    for candidate in (cn, skill_name):
        c = norm(candidate)
        if c in by_name:
            found = by_name[c]
            break
    if not found:
        for c in (norm(cn), norm(skill_name)):
            for name, hits in by_name.items():
                if c and (c in name or name in c):
                    found = hits
                    break
            if found:
                break

    print(f'{row["key"]:<10} id={row["item_id"]:<5} skill={row["skill"]:<5} '
          f'{CAMP.get(row["camp"], row["camp"]):<7} {cn}')
    print(f'           skill name : {skill_name}')
    print(f'           script     : {script}')
    if found:
        for map_id, scene, x, z, name in found[:3]:
            print(f'           -> map {map_id} ({scene}) {name!r} '
                  f'x={x} z={z}')
    else:
        print('           -> no matching landing point in Address.ini')
    print()
