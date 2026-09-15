import re, struct
line = open(".re/snap545.txt", encoding="utf-8", errors="replace").read()
m = re.search(r"hex=([0-9a-fA-F]+)", line)
hx = m.group(1); b = bytes.fromhex(hx)
print("len:", len(b))
for o in range(4, 120, 4):
    print(f"  +{o:>3}: {struct.unpack_from('<I', b, o)[0]:08X}", end="\n" if (o-4) % 16 == 12 else "")
print()
print("quest@8 =", struct.unpack_from('<I', b, 8)[0])
