"""Find capture evidence for the FlyBook teleport scrolls.

The client casts the scroll's skill (Magic.ini maps FlyBook n -> Skill), so the
capture should hold a skill-cast frame naming that skill id. Whatever the server
answers with next is the authoritative destination.
"""
import collections
import struct
import subprocess
import sys

DB = 'godswar'
FLY_SKILLS = set(range(3000, 3061)) | set(range(5626, 5632))


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


def frames(hexblob, opcode):
    data = bytes.fromhex(hexblob)
    out, off = [], 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        if op == opcode:
            out.append(data[off:off + length])
        off += length
    return out


print('=== skill-cast (10024) frames, by opcode + direction ===')
rows = query("""
    SELECT direction, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode = 10024
    ORDER BY id
    LIMIT 4000;
""")
seen = collections.Counter()
total = 0
for line in rows:
    direction, blob = line.split('|', 1)
    for frame in frames(blob, 10024):
        total += 1
        seen[(direction, len(frame))] += 1
print(f'parsed 10024 frames: {total}')
for k, v in seen.most_common(20):
    print(f'   direction={k[0]:<4} length={k[1]:<5} count={v}')

print()
print('=== scan every 10024 frame for a 16-bit value in the scroll skill set ===')
rows = query("""
    SELECT direction, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode = 10024
    ORDER BY id;
""")
hits = []
for line in rows:
    direction, blob = line.split('|', 1)
    for frame in frames(blob, 10024):
        for off in range(4, len(frame) - 1):
            value = struct.unpack_from('<H', frame, off)[0]
            if value in FLY_SKILLS:
                hits.append((direction, off, value, frame.hex()))
                break

print(f'frames whose payload names a scroll skill: {len(hits)}')
by_skill = collections.Counter(h[2] for h in hits)
for skill, count in sorted(by_skill.items()):
    print(f'   skill {skill}: {count} frame(s)')
print()
for direction, off, value, hexblob in hits[:10]:
    print(f'   {direction} skill={value} at +{off}: {hexblob}')
