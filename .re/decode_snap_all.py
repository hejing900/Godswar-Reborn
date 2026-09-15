import re, struct
rows = []
for line in open(".re/snap_all.txt", encoding="utf-8", errors="replace"):
    m = re.search(r"(\d\d:\d\d:\d\d\.\d+) LoginQuestSnapshot len=(\d+) op=10090 hex=([0-9a-fA-F]+)", line)
    if not m: continue
    b = bytes.fromhex(m.group(3)); n = struct.unpack_from('<I', b, 4)[0]
    desc = []
    for i in range(min(n, 4)):
        o = 8 + i * 96
        desc.append((struct.unpack_from('<I', b, o)[0], struct.unpack_from('<I', b, o+4)[0], struct.unpack_from('<I', b, o+8)[0],
                     struct.unpack_from('<I', b, o+40)[0], struct.unpack_from('<i', b, o+44)[0], struct.unpack_from('<i', b, o+56)[0],
                     struct.unpack_from('<i', b, o+68)[0], struct.unpack_from('<i', b, o+72)[0], struct.unpack_from('<i', b, o+80)[0]))
    rows.append((m.group(1), n, desc))
print(f"{len(rows)} 个 10090 帧")
for t, n, desc in rows:
    for (q, g, r, mon, w52, req, kind, w80, prog) in desc:
        print(f"{t} count={n} quest={q} giver={g} resp={r} +48={mon} +52={w52 if w52!=0 else 0}({'FFFFFFFF' if w52==-1 else w52}) +64={req} +76={kind} +80={w80} +88={prog}")
