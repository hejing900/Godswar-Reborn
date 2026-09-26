"""Locate the scroll skill ids anywhere in the capture.

Rather than assume which opcode carries a skill cast, scan every captured frame
for a little-endian 16-bit or 32-bit field equal to a FlyBook skill id, and
report which opcodes and directions carry them.
"""
import collections
import struct
import subprocess
import sys

DB = 'godswar'
FLY = {3000: 'Athens Portal', 3001: 'Athens Suburb', 3002: 'Marathon Portal',
       3003: 'Plataea Portal', 3004: 'Parnitha Portal',
       3005: 'Athens Thermopylae', 3025: 'Sparta Portal',
       3026: 'Sparta Suburb', 3027: 'Peloponnesus Portal',
       3028: 'Derveni Portal', 3029: 'Nemea Portal',
       3030: 'Sparta Thermopylae', 3031: 'Parnitha (new)',
       3032: 'Megara Coast', 3033: 'Corinth', 3034: 'Argolis',
       3035: 'Nemea (new)', 3036: 'Derveni (new)', 3037: 'Plataea (new)',
       3038: 'Corinth (Athens)', 3039: 'Corinth (Sparta)',
       3050: 'Hermes Stone', 5626: 'Athens Delphi', 5627: 'Sparta Delphi',
       5628: 'Athens Elasson', 5629: 'Sparta Elasson',
       5630: 'Athens Olympus', 5631: 'Sparta Olympus'}


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


print('scanning every frame for a scroll skill id ...')
rows = query("""
    SELECT opcode, direction, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IS NOT NULL
    ORDER BY id;
""")
print(f'rows: {len(rows)}')

hits = collections.defaultdict(list)
for line in rows:
    parts = line.split('|', 2)
    if len(parts) != 3:
        continue
    opcode, direction, blob = parts
    try:
        data = bytes.fromhex(blob)
    except ValueError:
        continue
    # The capture stores whole chunk buffers; walk the frames inside.
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        frame = data[off:off + length]
        for index in range(4, len(frame) - 3):
            v16 = struct.unpack_from('<H', frame, index)[0]
            v32 = struct.unpack_from('<I', frame, index)[0]
            if v16 in FLY or v32 in FLY:
                skill = v16 if v16 in FLY else v32
                hits[skill].append((op, direction, index, frame.hex()))
                break
        off += length

print()
print(f'skill ids found: {len(hits)}')
for skill in sorted(hits):
    sample = hits[skill][0]
    print(f'  skill {skill:<5} {FLY[skill]:<20} frames={len(hits[skill]):<4} '
          f'opcode={sample[0]} dir={sample[1]} at +{sample[2]}')

print()
print('=== sample frames ===')
for skill in sorted(hits):
    for op, direction, index, hexblob in hits[skill][:2]:
        print(f'  skill={skill} opcode={op} {direction} +{index}')
        print(f'     {hexblob}')
