"""Pull the whole newest capture session's transporter exchange.

The player re-clicked all six teleport entries. Every pick is a C2S 10069 on the
transporter npc; the reply that follows is either a 10070 page or a 10018
landing. Grouping by the npc that was opened keeps the six answers together even
when other npcs are clicked in between.
"""
import collections
import struct
import subprocess
import sys

DB = 'godswar'


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


sessions = query("""
    SELECT capture_session_id, COUNT(*), MIN(captured_at), MAX(captured_at)
    FROM packet_transactions
    GROUP BY capture_session_id
    ORDER BY MAX(captured_at) DESC;
""")
print('=== capture sessions (newest first) ===')
for line in sessions[:6]:
    print(f'  {line}')
newest = sessions[0].split('|')[0]
print()

rows = query(f"""
    SELECT id, captured_at, connection_id, direction, opcode,
           encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE capture_session_id = '{newest}'
      AND opcode IN (10067, 10068, 10069, 10070, 10018)
    ORDER BY id;
""")
print(f'dialogue frames in the newest session: {len(rows)}')
print()

stream = []
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
        stream.append((int(row_id), at, conn, direction, op, data[off:off + length]))
        off += length


def read_script(frame):
    raw = frame[16:]
    zero = raw.find(b'\x00')
    return raw[:zero if zero >= 0 else len(raw)].decode('ascii', 'replace')


def packed(frame, offset):
    out, value = [], struct.unpack_from('<I', frame, offset)[0]
    while value:
        value, digit = divmod(value, 1000)
        out.append(digit)
    return out


# Which npcs were opened, and with what menu.
opens = collections.OrderedDict()
for row_id, at, conn, direction, op, frame in stream:
    if op == 10067 and direction == 'S2C' and len(frame) >= 20:
        npc, = struct.unpack_from('<I', frame, 4)
        flags, = struct.unpack_from('<I', frame, 8)
        opens.setdefault(npc, (flags, tuple(packed(frame, 12)), read_script(frame)))

print('=== npcs opened in this session ===')
for npc, (flags, funcs, script) in opens.items():
    print(f'  npc={npc:<7} flags=0x{flags:<6X} functions={list(funcs)}  {script!r}')

print()
print('=== every pick on the transporter, with its answer ===')
TRANSPORTER = 5179
for index, (row_id, at, conn, direction, op, frame) in enumerate(stream):
    if op != 10069 or direction != 'C2S' or len(frame) < 24:
        continue
    npc, = struct.unpack_from('<I', frame, 4)
    if npc != TRANSPORTER:
        continue
    f8, = struct.unpack_from('<I', frame, 8)
    f16, = struct.unpack_from('<I', frame, 16)
    f20, = struct.unpack_from('<I', frame, 20)
    picked = f16 if f16 != 0xFFFFFFFF else f20
    label = 'OPEN (ask for page)' if picked == 0xFFFFFFFF else f'pick {picked}'
    print(f'{row_id:>7} {at[11:19]} page={f8} {label}')
    shown = 0
    for follow in stream[index + 1:]:
        if follow[2] != conn or follow[3] != 'S2C':
            continue
        f_id, f_at, _, _, f_op, f_frame = follow
        if f_op == 10070 and len(f_frame) >= 12:
            if struct.unpack_from('<I', f_frame, 4)[0] != TRANSPORTER:
                continue
            dialog, = struct.unpack_from('<I', f_frame, 8)
            vals = [struct.unpack_from('<I', f_frame, o)[0]
                    for o in range(12, len(f_frame) - 3, 4)]
            print(f'         -> 10070 dialog={dialog} values={vals}')
            shown += 1
        elif f_op == 10018 and len(f_frame) >= 28:
            x, = struct.unpack_from('<f', f_frame, 8)
            z, = struct.unpack_from('<f', f_frame, 16)
            mid, = struct.unpack_from('<H', f_frame, 20)
            print(f'         -> >>> LANDING map={mid} x={x:.1f} z={z:.1f}')
            shown += 1
        if shown >= 3:
            break
