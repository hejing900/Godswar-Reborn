import re, struct, pathlib
# 崩溃：本地时间 -> 地址
lines = pathlib.Path(r"D:\Godswar Origin\Dump\Error.log").read_text(encoding="utf-8", errors="replace").splitlines()
crashes = []
t = None
for ln in lines:
    m = re.search(r"Exception Time:\s+(\d+):(\d+):(\d+)\s+\((\d+)-(\d+)-(\d+)\)", ln)
    if m: t = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)):02d}"
    m = re.search(r"Fault address:\s+([0-9A-Fa-f]{8})", ln)
    if m and t: crashes.append((t, m.group(1).upper()))
# 快照：容器时间(UTC) = 本地-8
snaps = []
for ln in pathlib.Path(".re/snap_now.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    m = re.search(r"(\d\d):(\d\d):(\d\d)\.\d+ LoginQuestSnapshot len=\d+ op=10090 hex=([0-9a-fA-F]+)", ln)
    if not m: continue
    h, mi, s = (int(m.group(i)) for i in (1, 2, 3))
    loc = f"{(h+8)%24:02d}:{mi:02d}:{s:02d}"
    b = bytes.fromhex(m.group(4)); n = struct.unpack_from('<I', b, 4)[0]
    q = struct.unpack_from('<I', b, 8)[0] if n else 0
    snaps.append((loc, n, q))
print("今天最后 8 次崩溃（本地时间 / 地址）:")
for t, a in crashes[-8:]: print(f"  {t}  {a}")
print("\n登录快照（本地时间 / 携带任务数 / 任务号）:")
for loc, n, q in snaps[-10:]: print(f"  {loc}  count={n}  quest={q}")
