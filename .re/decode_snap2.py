import re, struct
for i, line in enumerate(open(".re/snap_last.txt", encoding="utf-8", errors="replace")):
    m = re.search(r"(\d\d:\d\d:\d\d\.\d+) LoginQuestSnapshot len=(\d+) op=10090 hex=([0-9a-fA-F]+)", line)
    if not m: continue
    b = bytes.fromhex(m.group(3))
    print(f"--- {m.group(1)} len={len(b)} count@4={struct.unpack_from('<I',b,4)[0]}")
    for o in range(8, 96, 4):
        print(f"  +{o:>3}: {struct.unpack_from('<I', b, o)[0]:08X}")
