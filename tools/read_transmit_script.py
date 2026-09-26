"""Read the client's teleport dialogue script.

Localization/<lang>/UI/XML/NpcFun/NpcFunTranmit.lua is the script the client runs
for NPC_FLAG_SYS_TRANMIT. Its branches decide what every number the server sends
draws, so it is the authority for the Event Transporter dialogue chain. The
capture shows the reference server opening that dialogue with dialog 1 =
[200, 700, 500, 600, 202]; this prints what each of those numbers is.
"""
import re
import sys

PATH = r'D:\Godswar Origin\Localization\en_us\UI\XML\NpcFun\NpcFunTranmit.lua'
LANG = r'D:\Godswar Origin\Localization\en_us\UI\Base\LuaText.lua'

text = open(PATH, 'rb').read().decode('utf-8-sig', 'replace')
lines = text.splitlines()
print(f'{PATH}')
print(f'lines: {len(lines)}')
print()

# Index branch guards: `if Index == N then` / `elseif SubID == N then`
print('=== structure: every Index and SubID branch, in file order ===')
depth_index = None
for number, line in enumerate(lines, 1):
    stripped = line.strip()
    m = re.match(r'if\s+Index\s*==\s*(\d+)\s+then', stripped)
    if m:
        print(f'  L{number:<5} Index == {m.group(1)}')
        continue
    m = re.match(r'elseif\s+Index\s*==\s*(\d+)\s+then', stripped)
    if m:
        print(f'  L{number:<5} Index == {m.group(1)}')
        continue
    m = re.match(r'(?:else)?if\s+SubID\s*==\s*(\d+)\s+then(.*)', stripped)
    if m:
        comment = m.group(2).strip()
        print(f'  L{number:<5}   SubID == {m.group(1):<6} {comment}')
        continue
    m = re.match(r'elseif\s+SubID\s*==\s*(\d+)\s+then(.*)', stripped)
    if m:
        comment = m.group(2).strip()
        print(f'  L{number:<5}   SubID == {m.group(1):<6} {comment}')

print()
print('=== the numbers the capture used: where does each appear? ===')
for wanted in (200, 700, 500, 600, 202, 900):
    hits = [n for n, line in enumerate(lines, 1)
            if re.search(rf'SubID\s*==\s*{wanted}\b', line)]
    print(f'  SubID {wanted:<5} -> lines {hits}')

print()
print('=== SubID 1 block (the main menu text) ===')
start = None
for n, line in enumerate(lines):
    if re.match(r'\s*if\s+SubID\s*==\s*1\s+then', line):
        start = n
        break
if start is not None:
    for n in range(start, min(start + 40, len(lines))):
        print(f'  {n + 1:>5} {lines[n]}')
