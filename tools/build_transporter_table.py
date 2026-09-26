"""Build the reference server's transporter table from the capture.

For every npc the player clicked, this pairs:
  * the 10067 the server sent when the npc was opened  (flags + function list)
  * each 10069 the client sent                          (function + picked entry)
  * what the server answered                            (10070 menu / 10018 landing)
so the destination of every menu entry can be read off instead of guessed.
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


rows = query("""
    SELECT id, connection_id, direction, opcode, encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IN (10067, 10068, 10069, 10070, 10018)
    ORDER BY id;
""")
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


# opens: npc -> (flags, functions, script)
opens = {}
for row_id, conn, direction, op, frame in stream:
    if op == 10067 and direction == 'S2C' and len(frame) >= 20:
        npc, = struct.unpack_from('<I', frame, 4)
        flags, = struct.unpack_from('<I', frame, 8)
        opens.setdefault(npc, set()).add(
            (flags, tuple(packed(frame, 12)), read_script(frame)))

print()
print('=== every npc the capture opened, with its function table ===')
for npc in sorted(opens):
    for flags, functions, script in sorted(opens[npc]):
        print(f'  npc={npc:<7} flags=0x{flags:<5X} functions={list(functions)}  '
              f'script={script!r}')

# picks and their answers
print()
print('=== pick -> answer, grouped by npc ===')
by_npc = collections.defaultdict(list)
for index, (row_id, conn, direction, op, frame) in enumerate(stream):
    if op != 10069 or direction != 'C2S' or len(frame) < 24:
        continue
    npc, = struct.unpack_from('<I', frame, 4)
    field8, = struct.unpack_from('<I', frame, 8)
    field16, = struct.unpack_from('<I', frame, 16)
    field20, = struct.unpack_from('<I', frame, 20)
    picked = field16 if field16 != 0xFFFFFFFF else field20
    if picked == 0xFFFFFFFF:
        continue
    answer = None
    for follow in stream[index + 1:]:
        if follow[1] != conn or follow[2] != 'S2C':
            continue
        _, _, _, f_op, f_frame = follow
        if f_op == 10070 and len(f_frame) >= 12:
            dialog, = struct.unpack_from('<I', f_frame, 8)
            values = [struct.unpack_from('<I', f_frame, o)[0]
                      for o in range(12, len(f_frame) - 3, 4)]
            answer = f'10070 dialog={dialog} values={values}'
            break
        if f_op == 10018 and len(f_frame) >= 28:
            x, = struct.unpack_from('<f', f_frame, 8)
            z, = struct.unpack_from('<f', f_frame, 16)
            mid, = struct.unpack_from('<H', f_frame, 20)
            answer = f'>>> LANDING map={mid} x={x:.1f} z={z:.1f}'
            break
    by_npc[npc].append((field8, picked, answer))

for npc in sorted(by_npc):
    scripts = {s for _, _, s in opens.get(npc, set())}
    print(f'  npc={npc}  script={sorted(scripts)}')
    for field8, picked, answer in by_npc[npc]:
        print(f'      page={field8:<4} picked={picked:<5} -> {answer}')
