import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
ref = {}
for r in q("select opcode, encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode in (10076,10082) order by id;"):
    op, hx = r.split("|"); op = int(op); b = bytes.fromhex(hx)
    if op == 10082:
        ref.setdefault(("ans", struct.unpack_from('<I', b, 12)[0]), b)
    else:
        ref.setdefault(("det", struct.unpack_from('<I', b, 8)[0]), b)
ours = {}
import re
for ln in open(".re/quest-frames.log", encoding="utf-8", errors="replace"):
    m = re.search(r"QuestAcceptAnswer len=\d+ op=10082 hex=([0-9a-fA-F]+)", ln)
    if m:
        b = bytes.fromhex(m.group(1)); ours[("ans", struct.unpack_from('<I', b, 12)[0])] = b
print("== reference answer full dwords (quest 1520, 1521, 1519, 518) ==")
for key in [("ans",x) for x in (518,519,520,1518,1519,1520,1521,1522)]:
    b = ref.get(key)
    if not b: continue
    print(f"  {key}: " + " ".join(f"{struct.unpack_from('<I',b,o)[0]:08X}" for o in range(4, 64, 4)))
print("== reference detail frames ==")
for (k, qid), b in sorted(ref.items()):
    if k != "det": continue
    print(f"  next={qid}: " + " ".join(f"{struct.unpack_from('<I',b,o)[0]:08X}" for o in range(4, 64, 4)))
print("== diff ours vs reference (answers) ==")
for key in sorted(set(ours) & set(ref)):
    a, b = ours[key], ref[key]
    diffs = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    print(f"  {key}: len ours={len(a)} ref={len(b)} ndiff={len(diffs)} first={diffs[:16]}")
