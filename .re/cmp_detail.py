import subprocess, struct, re
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
refdet = {}
for r in q("select encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode=10076 order by id;"):
    b = bytes.fromhex(r); refdet[struct.unpack_from('<I', b, 8)[0]] = b
oursdet = {}
for ln in open(".re/quest-frames.log", encoding="utf-8", errors="replace"):
    m = re.search(r"QuestNextDetail len=\d+ op=10076 hex=([0-9a-fA-F]+)", ln)
    if m:
        b = bytes.fromhex(m.group(1)); oursdet[struct.unpack_from('<I', b, 8)[0]] = b
def show(b, label):
    print(f"{label} len={len(b)}")
    print("   " + " ".join(f"+{o}:{struct.unpack_from('<I',b,o)[0]:08X}" for o in range(4, 72, 4)))
for qid in sorted(refdet):
    show(refdet[qid], f"REF  detail next={qid}")
for qid in sorted(oursdet):
    if qid in refdet:
        a, b = oursdet[qid], refdet[qid]
        d = [i for i in range(min(len(a),len(b))) if a[i]!=b[i]]
        print(f"OURS detail next={qid} ndiff={len(d)} first={d[:12]}")
        show(a, f"OURS detail next={qid}")
