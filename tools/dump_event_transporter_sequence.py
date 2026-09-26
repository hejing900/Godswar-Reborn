"""Dump the Event Transporter exchange in capture order.

Athens' Event Transporter is Athens_072, object id 5210. Its function table is
1, and the script entries seen are 200/700/500/600/202. This prints every frame
touching npc 5210 in the order the capture recorded them, plus the following 60
frames on the same connection so whatever the server did after a choice is
visible.
"""
import struct
import subprocess
import sys

DB = 'godswar'
NPC = 5210


def query(sql):
    done = subprocess.run(
        ['docker', 'exec', 'godswar-postgres', 'psql', '-U', 'godswar',
         '-d', DB, '-t', '-A', '-F', '|', '-c', sql],
        capture_output=True, text=True, encoding='utf-8')
    if done.returncode != 0:
        sys.stderr.write(done.stderr or '')
        raise SystemExit(1)
    return [l for l in (done.stdout or '').splitlines() if l.strip()]


# Read the whole stream in id order, keeping the connection so a follow-up can
# be attributed to the right session.
rows = query("""
    SELECT id, captured_at, connection_id, direction, opcode,
           encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IS NOT NULL
    ORDER BY id;
""")
print(f'rows: {len(rows)}')

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
        stream.append((int(row_id), conn, direction, op, data[off:off + length]))
        off += length

print(f'frames: {len(stream)}')


def names_npc(frame):
    if len(frame) < 8:
        return False
    try:
        value, = struct.unpack_from('<I', frame, 4)
    except struct.error:
        return False
    return value == NPC


def read_script(frame):
    raw = frame[16:]
    zero = raw.find(b'\x00')
    return raw[:zero if zero >= 0 else len(raw)].decode('ascii', 'replace')


def packed(frame, offset):
    if len(frame) < offset + 4:
        return []
    out, value = [], struct.unpack_from('<I', frame, offset)[0]
    while value:
        value, digit = divmod(value, 1000)
        out.append(digit)
    return out


hits = [index for index, item in enumerate(stream) if names_npc(item[4])]
print(f'frames naming npc {NPC}: {len(hits)}')
print()

for index in hits:
    row_id, conn, direction, op, frame = stream[index]
    print(f'--- id={row_id} {direction} opcode={op} len={len(frame)} ---')
    print(f'    {frame.hex()}')
    if op == 10067 and direction == 'S2C':
        flags, = struct.unpack_from('<I', frame, 8)
        print(f'    flags=0x{flags:X}  functions={packed(frame, 12)}  '
              f'script={read_script(frame)!r}')
    if op == 10070 and direction == 'S2C':
        dialog, = struct.unpack_from('<I', frame, 8)
        rest = [struct.unpack_from('<I', frame, o)[0]
                for o in range(12, len(frame) - 3, 4)]
        print(f'    dialog={dialog}  values={rest}')
    if op == 10069 and direction == 'C2S':
        f8, = struct.unpack_from('<I', frame, 8)
        f16, = struct.unpack_from('<I', frame, 16)
        f20, = struct.unpack_from('<I', frame, 20)
        print(f'    +8={f8} +16={f16} +20(clicked)={f20}')

    # Show the next few frames on the same connection.
    print('    ... following frames on this connection:')
    shown = 0
    for follow in stream[index + 1:]:
        if follow[1] != conn:
            continue
        f_id, _, f_dir, f_op, f_frame = follow
        if f_op in (10015, 10016, 10017, 10194) and shown > 14:
            continue
        print(f'      id={f_id} {f_dir} op={f_op} len={len(f_frame)} '
              f'{f_frame[:40].hex()}')
        shown += 1
        if shown >= 18:
            break
    print()
