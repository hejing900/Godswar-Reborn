"""Find the Event Transporter NPC in the capture and follow what it does.

Athens' Event Transporter is Athens_072 (object id 5211, at 143,-39). Its script
carries two entries - 700 "Teleport to Sicily" and 900 "To the Trojan
Expedition". This pulls every frame that relates to that npc: the click answer
(10067), the function replies (10070), and whatever the server sends after the
player picks an entry, so the real transport sequence can be read off.
"""
import collections
import struct
import subprocess
import sys

DB = 'godswar'
# Athens_072 = 5211, Sparta_072 is the same npc in the other capital.
CANDIDATE_IDS = {5211, 5210, 5212}

# Opcodes worth looking at.
INTERESTING = {10067, 10068, 10069, 10070, 10018, 10021, 10201, 10020, 10071}


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


def frames(blob):
    data = bytes.fromhex(blob)
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        yield op, data[off:off + length]
        off += length


print('scanning the capture for frames that name the Event Transporter ...')
rows = query("""
    SELECT id, captured_at, direction, opcode, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IS NOT NULL
    ORDER BY id;
""")
print(f'rows: {len(rows)}')

hits = []
for line in rows:
    parts = line.split('|', 4)
    if len(parts) != 5:
        continue
    row_id, at, direction, opcode, blob = parts
    try:
        data = bytes.fromhex(blob)
    except ValueError:
        continue
    for op, frame in frames(blob):
        if op not in INTERESTING or len(frame) < 8:
            continue
        value, = struct.unpack_from('<I', frame, 4)
        if value in CANDIDATE_IDS:
            hits.append((int(row_id), at, direction, op, value, frame))

print(f'frames naming an Event Transporter id: {len(hits)}')
print()
print(f'{"id":>7} {"dir":<4} {"opcode":>6} {"npc":>6}  frame')
print('-' * 100)
for row_id, at, direction, op, value, frame in hits[:80]:
    print(f'{row_id:>7} {direction:<4} {op:>6} {value:>6}  {frame.hex()}')

print()
print('=== tally ===')
tally = collections.Counter((op, direction) for _, _, direction, op, _, _ in hits)
for (op, direction), count in tally.most_common():
    print(f'  opcode {op} {direction}: {count}')

print()
print('=== any 10070 (function reply) whose dialog index is 1 ===')
for row_id, at, direction, op, value, frame in hits:
    if op == 10070 and len(frame) >= 12:
        dialog, = struct.unpack_from('<I', frame, 8)
        print(f'  id={row_id} npc={value} dialog={dialog} {frame.hex()}')
