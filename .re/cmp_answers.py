import re, struct, subprocess
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def ref_frames(op):
    q = f"select encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and opcode={op} order by id;"
    out = subprocess.run(PSQL+[q], capture_output=True, text=True, check=True).stdout.split()
    return [bytes.fromhex(x) for x in out if x]
def slots(b, area_offsets, label):
    print(f"  {label} len={len(b)} quest={struct.unpack_from('<I',b,12)[0] if len(b)>=16 else 0}")
    for base in area_offsets:
        for i in range(4):
            s = base + i*72
            if s+32 > len(b): break
            item, count = struct.unpack_from("<iI", b, s)
            print(f"     area@{base} slot{i} item={item} count={count} tag={b[s+0x1b]}")
ours = {}
for ln in open(".re/quest-frames.log", encoding="utf-8", errors="replace"):
    m = re.search(r"(\d\d:\d\d:\d\d\.\d+) QuestAcceptAnswer len=\d+ op=10082 hex=([0-9a-fA-F]+)", ln)
    if m:
        b = bytes.fromhex(m.group(2)); q = struct.unpack_from("<I", b, 12)[0]
        ours[q] = b
print("### OUR ANSWERS (slots at +72 and +360)")
for q in sorted(ours):
    slots(ours[q], [72, 360], f"ours quest={q}")
print("### REFERENCE ANSWERS (first capture per quest)")
refs = {}
for b in ref_frames(10082):
    if len(b) != 648: continue
    q = struct.unpack_from("<I", b, 12)[0]
    if q in (1519,1520,1521,1522,518,519,520) and q not in refs:
        refs[q] = b
for q in sorted(refs):
    slots(refs[q], [72, 360], f"ref quest={q}")
