"""Decode the newest NPC dialogue exchange straight out of the live capture.

The proxy is capturing into the `godswar` database right now. This pulls the
tail of that stream, keeps the NPC dialogue frames, and prints them in order so
the six teleport entries and every reply after them can be read off.
"""
import struct
import subprocess
import sys

DB = 'godswar'
# Only look at what arrived in the last few minutes.
WINDOW_MINUTES = 30

DIALOGUE = {10067: 'NPC-OPEN', 10068: 'NPC-PAGE', 10069: 'NPC-ACT',
            10070: 'NPC-MENU', 10018: 'LANDING'}


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
    WHERE opcode IN (10067, 10068, 10069, 10070, 10018)
      AND captured_at > now() - interval '{WINDOW_MINUTES} minutes'
    ORDER BY id;
""")
print(f'dialogue frames in the last {WINDOW_MINUTES} minutes: {len(rows)}')
print()

for line in rows:
    parts = line.split('|', 5)
    if len(parts) != 6:
        continue
    row_id, at, conn, direction, opcode, blob = parts
    try:
        data = bytes.fromhex(blob)
    except ValueError:
        continue
    off = 0
    while off + 4 <= len(data):
        length, op = struct.unpack_from('<HH', data, off)
        if length < 4 or off + length > len(data):
            break
        frame = data[off:off + length]
        tag = DIALOGUE.get(op, str(op))
        detail = ''
        if op == 10067 and len(frame) >= 20:
            npc, = struct.unpack_from('<I', frame, 4)
            flags, = struct.unpack_from('<I', frame, 8)
            packed, = struct.unpack_from('<I', frame, 12)
            funcs, value = [], packed
            while value:
                value, digit = divmod(value, 1000)
                funcs.append(digit)
            raw = frame[16:]
            zero = raw.find(b'\x00')
            script = raw[:zero if zero >= 0 else len(raw)].decode('ascii', 'replace')
            detail = (f'npc={npc} flags=0x{flags:X} functions={funcs} '
                      f'script={script!r}')
        elif op == 10068 and len(frame) >= 8:
            npc, = struct.unpack_from('<I', frame, 4)
            detail = f'npc={npc}'
        elif op == 10069 and len(frame) >= 24:
            npc, = struct.unpack_from('<I', frame, 4)
            f8, = struct.unpack_from('<I', frame, 8)
            f12, = struct.unpack_from('<I', frame, 12)
            f16, = struct.unpack_from('<I', frame, 16)
            f20, = struct.unpack_from('<I', frame, 20)
            detail = (f'npc={npc} +8={f8} +12={f12} '
                      f'+16={f16} +20={f20}')
        elif op == 10070 and len(frame) >= 12:
            npc, = struct.unpack_from('<I', frame, 4)
            dialog, = struct.unpack_from('<I', frame, 8)
            vals = [struct.unpack_from('<I', frame, o)[0]
                    for o in range(12, len(frame) - 3, 4)]
            detail = f'npc={npc} dialog={dialog} values={vals}'
        elif op == 10018 and len(frame) >= 28:
            obj, = struct.unpack_from('<I', frame, 4)
            x, = struct.unpack_from('<f', frame, 8)
            z, = struct.unpack_from('<f', frame, 16)
            mid, = struct.unpack_from('<H', frame, 20)
            detail = f'obj={obj} map={mid} x={x:.2f} z={z:.2f}'
        print(f'{row_id:>7} {at[11:19]} {direction:<4} {tag:<8} '
              f'len={len(frame):<4} {detail}')
        off += length
