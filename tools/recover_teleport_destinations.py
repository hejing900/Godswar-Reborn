"""Recover teleport destinations from the capture by reading what follows a cast.

A teleport ends in a map transition, which the reference server announces with
opcode 10018 (28 bytes: +4 object id, +8 f32 X, +12 ?, +16 f32 Z, +20 map id in
the low 16 bits, +24 = 1). So: find a C2S frame that names a FlyBook skill, then
report the 10018 frame that follows on the same connection.
"""
import collections
import struct
import subprocess
import sys

DB = 'godswar'
SKILLS = {
    3000: 'FlyBook1  Athens Portal', 3001: 'FlyBook2  Athens Suburb',
    3002: 'FlyBook3  Marathon Portal', 3003: 'FlyBook4  Plataea Portal',
    3004: 'FlyBook20 Parnitha Port', 3005: 'FlyBook22 Athens Thermopylae',
    3025: 'FlyBook5  Sparta Portal', 3026: 'FlyBook6  Sparta Suburb',
    3027: 'FlyBook7  Peloponnesus', 3028: 'FlyBook8  Derveni',
    3029: 'FlyBook21 Nemea Forest', 3030: 'FlyBook23 Sparta Thermopylae',
    3031: 'FlyBook11 Parnitha', 3032: 'FlyBook12 Megara Coast',
    3033: 'FlyBook13 Corinth', 3034: 'FlyBook14 Argolis',
    3035: 'FlyBook15 Nemea', 3036: 'FlyBook16 Advanced Derveni',
    3037: 'FlyBook17 Mystic Plataea', 3038: 'FlyBook18 Athenian Corinth',
    3039: 'FlyBook19 Spartan Corinth', 3050: 'FlyBook9  Hermes Stone',
    5626: 'FlyBook24 Athens Delphi', 5627: 'FlyBook25 Sparta Delphi',
    5628: 'FlyBook26 Athens Elasson', 5629: 'FlyBook27 Sparta Elasson',
    5630: 'FlyBook28 Athens Olympus', 5631: 'FlyBook29 Sparta Olympus',
}
# The cast frame seen in the capture is 20 bytes with the skill at +8.
CAST_LEN = 20
CAST_SKILL_OFFSET = 8


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


print('loading the ordered packet stream ...')
rows = query("""
    SELECT id, captured_at, direction, opcode, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IS NOT NULL
    ORDER BY id;
""")
print(f'rows: {len(rows)}')

events = []   # (row id, opcode, direction, frame bytes)
for line in rows:
    parts = line.split('|', 4)
    if len(parts) != 5:
        continue
    row_id, at, direction, opcode, blob = parts
    try:
        data = bytes.fromhex(blob)
    except ValueError:
        continue
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        events.append((int(row_id), op, direction, data[off:off + length]))
        off += length

print(f'frames: {len(events)}')
print()

# Index the 10018 frames in stream order.
transitions = [
    (rid, frame) for rid, op, direction, frame in events
    if op == 10018 and direction == 'S2C' and len(frame) >= 28
]
print(f'10018 (map transition) frames: {len(transitions)}')
print()


def decode_10018(frame):
    obj, = struct.unpack_from('<I', frame, 4)
    x, = struct.unpack_from('<f', frame, 8)
    mid, = struct.unpack_from('<H', frame, 20)
    z, = struct.unpack_from('<f', frame, 16)
    return obj, x, z, mid


print('=== 10018 samples ===')
for rid, frame in transitions[:6]:
    obj, x, z, mid = decode_10018(frame)
    print(f'  id={rid} obj={obj} map={mid} x={x:.2f} z={z:.2f}')

print()
print('=== each scroll cast, and the 10018 that follows it ===')
casts = [(rid, struct.unpack_from('<H', f, CAST_SKILL_OFFSET)[0], f)
         for rid, op, direction, f in events
         if op == 10194 and direction == 'C2S' and len(f) == CAST_LEN
         and struct.unpack_from('<H', f, CAST_SKILL_OFFSET)[0] in SKILLS]
print(f'casts found: {len(casts)}')
print()

results = collections.defaultdict(list)
for rid, skill, frame in casts:
    following = [(trid, f) for trid, f in transitions if trid > rid]
    if not following:
        continue
    trid, tf = following[0]
    obj, x, z, mid = decode_10018(tf)
    gap = trid - rid
    if gap > 400:      # too far away to be the answer to this cast
        continue
    results[skill].append((mid, x, z, gap))

print(f'{"skill":>5}  {"scroll":<32} {"map":>4} {"x":>10} {"z":>10} {"gap":>6}')
print('-' * 76)
for skill in sorted(results):
    seen = {}
    for mid, x, z, gap in results[skill]:
        seen.setdefault((mid, round(x, 1), round(z, 1)), []).append(gap)
    for (mid, x, z), gaps in sorted(seen.items()):
        print(f'{skill:>5}  {SKILLS[skill]:<32} {mid:>4} {x:>10.1f} {z:>10.1f} '
              f'{min(gaps):>6}')

print()
print('=== scrolls with no transition found ===')
for skill in sorted(SKILLS):
    if skill not in results:
        print(f'  {skill:>5} {SKILLS[skill]}')
