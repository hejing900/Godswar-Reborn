"""Show the frames around the Athens transporter's successful teleport.

id 183607 is the C2S pick "4" on npc 5179 (Athens_041). Whatever the server sent
next is the answer; the frames before it say where the character was standing,
which tells an arrival coordinate apart from a departure one.
"""
import struct
import subprocess
import sys

DB = 'godswar'
PICK_ID = 183607
NPC = 5179


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


rows = query(f"""
    SELECT id, captured_at, connection_id, direction, opcode,
           encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE id BETWEEN {PICK_ID - 30} AND {PICK_ID + 40}
    ORDER BY id;
""")

KEY = {10015: 'MAPREADY?', 10016: 'SPAWN+', 10017: 'REMOVE-', 10018: 'LANDING',
       10020: 'WORLDOBJ', 10067: 'NPC-OPEN', 10068: 'NPC-PAGE', 10069: 'NPC-ACT',
       10070: 'NPC-MENU', 10038: 'NOTE', 10194: 'MOVE'}

for line in rows:
    parts = line.split('|', 5)
    if len(parts) != 6:
        continue
    row_id, at, conn, direction, opcode, blob = parts
    data = bytes.fromhex(blob)
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        frame = data[off:off + length]
        tag = KEY.get(op, '')
        detail = ''
        if op == 10018 and len(frame) >= 28:
            obj, = struct.unpack_from('<I', frame, 4)
            x, = struct.unpack_from('<f', frame, 8)
            z, = struct.unpack_from('<f', frame, 16)
            mid, = struct.unpack_from('<H', frame, 20)
            tail, = struct.unpack_from('<I', frame, 24)
            detail = f'obj={obj} map={mid} x={x:.2f} z={z:.2f} tail={tail}'
        elif op in (10016, 10017) and len(frame) >= 28:
            obj, = struct.unpack_from('<I', frame, 4)
            x, = struct.unpack_from('<f', frame, 8)
            z, = struct.unpack_from('<f', frame, 16)
            detail = f'obj={obj} x={x:.2f} z={z:.2f}'
        elif op == 10069 and len(frame) >= 24:
            npc, = struct.unpack_from('<I', frame, 4)
            f8, = struct.unpack_from('<I', frame, 8)
            f16, = struct.unpack_from('<I', frame, 16)
            f20, = struct.unpack_from('<I', frame, 20)
            detail = f'npc={npc} f8={f8} f16={f16} f20={f20}'
        elif op == 10070 and len(frame) >= 12:
            npc, = struct.unpack_from('<I', frame, 4)
            dialog, = struct.unpack_from('<I', frame, 8)
            vals = [struct.unpack_from('<I', frame, o)[0]
                    for o in range(12, len(frame) - 3, 4)]
            detail = f'npc={npc} dialog={dialog} values={vals}'
        elif op == 10067 and len(frame) >= 20:
            npc, = struct.unpack_from('<I', frame, 4)
            raw = frame[16:]
            zero = raw.find(b'\x00')
            script = raw[:zero if zero >= 0 else len(raw)].decode('ascii', 'replace')
            detail = f'npc={npc} script={script!r}'
        elif op == 10194 and len(frame) >= 20:
            x, = struct.unpack_from('<f', frame, 12)
            z, = struct.unpack_from('<f', frame, 16)
            detail = f'x={x:.2f} z={z:.2f}'
        mark = '  <<<< PICK' if int(row_id) == PICK_ID else ''
        print(f'{row_id:>7} {direction:<4} {op:>6} {tag:<9} len={len(frame):<4} '
              f'{detail}{mark}')
        off += length
