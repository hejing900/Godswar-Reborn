import re, struct
lines = open(".re/quest-frames.log", encoding="utf-8", errors="replace").read().splitlines()
def frames(kind):
    out = []
    for ln in lines:
        m = re.search(r"(\d\d:\d\d:\d\d\.\d+) (\w+) len=(\d+) op=(\d+) hex=([0-9a-fA-F]+)", ln)
        if not m: continue
        if m.group(2) != kind: continue
        b = bytes.fromhex(m.group(5))
        out.append((m.group(1), b, ln))
    return out
def show(b, label):
    print(f"--- {label} len={len(b)}")
    q = struct.unpack_from("<I", b, 12)[0]
    print(f"    quest={q} +16={struct.unpack_from('<I',b,16)[0]:08X} +28={struct.unpack_from('<I',b,28)[0]} +36={struct.unpack_from('<I',b,36)[0]}")
    # reward slot areas: answer 648 bytes -> two areas of 288 from +64 ; detail 356 -> one area from +60
    areas = [(64, 288), (352, 288)] if len(b) >= 640 else [(60, 288)]
    for base, size in areas:
        for i in range(size // 72):
            s = base + i * 72
            if s + 32 > len(b): break
            item, count = struct.unpack_from("<iI", b, s)
            print(f"    area@{base} slot{i}: item={item} count={count} byte1b={b[s+0x1b] if s+0x1b < len(b) else -1}")
for t, b, ln in frames("QuestAcceptAnswer"):
    show(b, f"{t} accept-answer")
for t, b, ln in frames("QuestNextDetail"):
    show(b, f"{t} next-detail")
