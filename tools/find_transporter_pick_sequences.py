"""Find a complete Event Transporter exchange: a click that actually picks an entry.

The Athens Event Transporter (Athens_072, object 5210) answers function 1 with
dialog 1 = [200, 700, 500, 600, 202]. What the reference server does when the
player picks 700 ("teleport to Sicily") or 900 is the part we need; this scans
every function reply that follows a genuine pick, across all npcs, so the
transport sequence can be identified even when the pick happens on the other
capital's transporter.
"""
import struct
import subprocess
import sys

DB = 'godswar'
TRANSPORT_FUNCTIONS = {1, 3, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 1088, 1089, 1090}


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
    SELECT id, connection_id, direction, opcode, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IN (10067, 10069, 10070, 10018)
    ORDER BY id;
""")
print(f'rows: {len(rows)}')

stream = []
for line in rows:
    parts = line.split('|', 4)
    if len(parts) != 5:
        continue
    row_id, conn, direction, opcode, blob = parts
    try:
        data = bytes.fromhex(blob)
    except ValueError:
        continue
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        stream.append((int(row_id), conn, direction, op, data[off:off + length]))
        off += length

print(f'frames: {len(stream)}')

# Collect the C2S 10069 frames that carry a real pick (not -1) in the last slot.
picks = []
for index, (row_id, conn, direction, op, frame) in enumerate(stream):
    if op != 10069 or direction != 'C2S' or len(frame) < 24:
        continue
    npc, = struct.unpack_from('<I', frame, 4)
    field8, = struct.unpack_from('<I', frame, 8)
    field12, = struct.unpack_from('<I', frame, 12)
    field16, = struct.unpack_from('<I', frame, 16)
    field20, = struct.unpack_from('<I', frame, 20)
    picked = field16 if field16 != 0xFFFFFFFF else field20
    if picked == 0xFFFFFFFF:
        continue
    picks.append((index, row_id, conn, npc, field8, field12, picked))

print(f'10069 frames with a real pick: {len(picks)}')
print()

# For each pick, show the next 10070/10018/10067 on the same connection.
print('=== pick -> what the server answered next ===')
for index, row_id, conn, npc, field8, field12, picked in picks:
    answers = []
    for follow in stream[index + 1:]:
        if follow[1] != conn:
            continue
        f_id, _, f_dir, f_op, f_frame = follow
        if f_dir != 'S2C':
            continue
        if f_op == 10070 and len(f_frame) >= 12:
            dialog, = struct.unpack_from('<I', f_frame, 8)
            values = [struct.unpack_from('<I', f_frame, o)[0]
                      for o in range(12, len(f_frame) - 3, 4)]
            answers.append(f'10070 dialog={dialog} values={values}')
        elif f_op == 10018 and len(f_frame) >= 28:
            x, = struct.unpack_from('<f', f_frame, 8)
            z, = struct.unpack_from('<f', f_frame, 16)
            mid, = struct.unpack_from('<H', f_frame, 20)
            answers.append(f'>>> 10018 LANDING map={mid} x={x:.1f} z={z:.1f}')
        elif f_op == 10067 and len(f_frame) >= 20:
            answers.append(f'10067 (reopen)')
        if len(answers) >= 6:
            break
    if answers:
        print(f'  id={row_id} npc={npc} f8={field8} f12={field12} picked={picked}')
        for answer in answers:
            print(f'      {answer}')
