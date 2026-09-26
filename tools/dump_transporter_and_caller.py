"""Find the reference server's answer for the two npcs that will not open.

The report is specific: only the Transporter and the instance caller fail, every
other npc works. Both are endpoints keyed by an exact (npc key, interaction id)
pair, so this pulls the reference server's own open frame for each of them and
prints the function table plus the first page it answered.
"""
import collections
import struct
import subprocess
import sys

DB = 'godswar'

# Athens Transporter (Athens_041) and the instance caller (Athens_060), plus
# Sparta's counterparts for comparison.
WANTED_SCRIPT = {'Athens_041', 'Athens_060', 'Sparta_042', 'Sparta_060'}
WANTED_NPC = {5179, 5180, 5199, 5198, 5200, 5039, 5057}


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
    SELECT id, captured_at, connection_id, direction, opcode,
           encode(clear_bytes,'hex')
    FROM packet_transactions
    WHERE opcode IN (10067, 10068, 10069, 10070)
    ORDER BY id;
""")
print(f'dialogue rows: {len(rows)}')

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
        frame = data[off:off + length]
        if op == 10067 and len(frame) >= 20:
            raw = frame[16:]
            zero = raw.find(b'\x00')
            script = raw[:zero if zero >= 0 else len(raw)].decode('ascii', 'replace')
            if script in WANTED_SCRIPT:
                stream.append((int(row_id), at, conn, direction, op, frame, script))
        elif op in (10068, 10069, 10070) and len(frame) >= 8:
            npc, = struct.unpack_from('<I', frame, 4)
            if npc in WANTED_NPC:
                stream.append((int(row_id), at, conn, direction, op, frame, ''))
        off += length

print(f'transporter / caller frames: {len(stream)}')
print()

for row_id, at, conn, direction, op, frame, script in stream:
    if op == 10067:
        npc, = struct.unpack_from('<I', frame, 4)
        flags, = struct.unpack_from('<I', frame, 8)
        packed, = struct.unpack_from('<I', frame, 12)
        funcs, value = [], packed
        while value:
            value, digit = divmod(value, 1000)
            funcs.append(digit)
        print(f'{row_id:>7} {at[11:19]} {direction} 10067 npc={npc} '
              f'flags=0x{flags:X} functions={funcs} script={script!r}')
    elif op == 10068:
        npc, = struct.unpack_from('<I', frame, 4)
        print(f'{row_id:>7} {at[11:19]} {direction} 10068 npc={npc} (ask page)')
    elif op == 10069:
        npc, = struct.unpack_from('<I', frame, 4)
        fields = [struct.unpack_from('<I', frame, o)[0]
                  for o in range(8, min(len(frame), 28), 4)]
        print(f'{row_id:>7} {at[11:19]} {direction} 10069 npc={npc} '
              f'fields={fields}')
    elif op == 10070:
        npc, = struct.unpack_from('<I', frame, 4)
        dialog, = struct.unpack_from('<I', frame, 8)
        vals = [struct.unpack_from('<I', frame, o)[0]
                for o in range(12, len(frame) - 3, 4)]
        print(f'{row_id:>7} {at[11:19]} {direction} 10070 npc={npc} '
              f'dialog={dialog} values={vals}')
