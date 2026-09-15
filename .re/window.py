import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:400]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
rows = q("select opcode, encode(clear_bytes,'hex'), captured_at from packet_transactions where captured_at between '2026-09-14 01:05' and '2026-09-14 01:15' order by id;")
print(f"{len(rows)} frames in window")
for r in rows:
    op, hx, ts = r.split("|")
    b = bytes.fromhex(hx)
    op = int(op)
    if op in (10030, 10084, 10086, 10076, 10166):
        body = " ".join(f"{struct.unpack_from('<I', b, o)[0]:08X}" for o in range(4, min(len(b), 40), 4))
        print(f"{ts} op={op:<6} len={len(b):>4} : {body}")
