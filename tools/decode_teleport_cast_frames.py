"""Decode the C2S 10194 frame that carries a teleport scroll cast.

Observed shape (20 bytes):
  +0  u16 length (0x14)
  +2  u16 opcode (0x27d2 = 10194)
  +4  u16 ?  (varies: 0001, 0002, 000b ...)
  +6  u16 ?  (const 0002)
  +8  u16 skill id   (e.g. 0x0bb9 = 3001)
  +10 f32 x
  +14 f32 z
  +18 u16 ?
"""
import struct
import subprocess
import sys

DB = 'godswar'
NAMES = {
    3000: 'FlyBook1  Athens Portal Scroll',
    3001: 'FlyBook2  Athens Suburb Scroll',
    3002: 'FlyBook3  Marathon Portal Scroll',
    3003: 'FlyBook4  Plataea Portal Scroll',
    3004: 'FlyBook20 Parnitha Port Portal Scroll',
    3005: 'FlyBook22 Athens Thermopylae Portal Scroll',
    3025: 'FlyBook5  Sparta Portal Scroll',
    3026: 'FlyBook6  Sparta Suburb Scroll',
    3027: 'FlyBook7  Peloponnesus Portal Scroll',
    3028: 'FlyBook8  Derveni Portal Scroll',
    3029: 'FlyBook21 Nemea Forest Portal Scroll',
    3030: 'FlyBook23 Sparta Thermopylae Portal Scroll',
    3031: 'FlyBook11 Parnitha Portal Scroll',
    3032: 'FlyBook12 Megara Coast Portal Scroll',
    3033: 'FlyBook13 Corinth Portal Scroll',
    3034: 'FlyBook14 Argolis Portal Scroll',
    3035: 'FlyBook15 Nemea Portal Scroll',
    3036: 'FlyBook16 Advanced Derveni Portal Scroll',
    3037: 'FlyBook17 Mystic Plataea Portal Scroll',
    3038: 'FlyBook18 Athenian Corinth Scroll',
    3039: 'FlyBook19 Spartan Corinth Scroll',
    3050: 'FlyBook9  Hermes Stone (Escape)',
    5626: 'FlyBook24 Athens Delphi Forest Scroll',
    5627: 'FlyBook25 Sparta Delphi Forest Scroll',
    5628: 'FlyBook26 Athens Elasson Portal Scroll',
    5629: 'FlyBook27 Sparta Elasson Portal Scroll',
    5630: 'FlyBook28 Athens Olympus Portal Scroll',
    5631: 'FlyBook29 Sparta Olympus Portal Scroll',
}


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
    SELECT id, captured_at, direction, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode = 10194
    ORDER BY id;
""")
print(f'10194 rows: {len(rows)}')

decoded = []
for line in rows:
    parts = line.split('|', 3)
    if len(parts) != 4:
        continue
    row_id, at, direction, blob = parts
    data = bytes.fromhex(blob)
    off = 0
    while off + 4 <= len(data):
        length, opcode = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        frame = data[off:off + length]
        if opcode == 10194 and len(frame) >= 20:
            skill, = struct.unpack_from('<H', frame, 8)
            if skill in NAMES:
                x, z = struct.unpack_from('<ff', frame, 10)
                decoded.append((row_id, at, direction,
                                struct.unpack_from('<H', frame, 4)[0],
                                struct.unpack_from('<H', frame, 6)[0],
                                skill, x, z,
                                struct.unpack_from('<H', frame, 18)[0]))
        off += length

print(f'frames naming a scroll skill: {len(decoded)}')
print()
print(f'{"skill":>5}  {"scroll":<40} {"f4":>4} {"f6":>4} {"x":>12} {"z":>12} {"f18":>5}')
print('-' * 92)
for _, _, _, f4, f6, skill, x, z, f18 in decoded:
    print(f'{skill:>5}  {NAMES[skill]:<40} {f4:>4} {f6:>4} '
          f'{x:>12.3f} {z:>12.3f} {f18:>5}')

print()
print('=== distinct skill -> emitted coordinate pairs ===')
import collections
pairs = collections.defaultdict(set)
for _, _, _, _, _, skill, x, z, _ in decoded:
    pairs[skill].add((round(x, 1), round(z, 1)))
for skill in sorted(pairs):
    coords = sorted(pairs[skill])
    print(f'  {skill:>5} {NAMES[skill]:<40} {len(coords):>3} point(s)')
    for x, z in coords[:6]:
        print(f'          x={x:<10} z={z}')
