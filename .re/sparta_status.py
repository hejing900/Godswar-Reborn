import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
rows = q("select coalesce(opcode,0), encode(clear_bytes,'hex'), captured_at from packet_transactions where captured_at between '2026-09-13 00:00' and '2026-09-13 00:05' and opcode in (10166,10086,10030) order by id;")
print(f"{len(rows)} rows")
n=0
for r in rows:
    op, hx, ts = r.split("|"); op = int(op); b = bytes.fromhex(hx)
    if op == 10166 and len(b) > 200:
        print(f"{ts} 10166 w96={struct.unpack_from('<I',b,96)[0]:>6} w100={struct.unpack_from('<I',b,100)[0]:>3} w228={struct.unpack_from('<I',b,228)[0]:>3} w120={struct.unpack_from('<I',b,120)[0]}")
    elif op in (10086,10030):
        body = " ".join(f"{struct.unpack_from('<I', b, o)[0]:08X}" for o in range(4, min(len(b), 40), 4))
        print(f"{ts} op={op} len={len(b)} : {body}")
    n+=1
    if n > 40: break
