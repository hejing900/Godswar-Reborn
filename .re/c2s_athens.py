import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:400]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
rows = q("select direction, opcode, encode(clear_bytes,'hex'), captured_at from packet_transactions where opcode in (10084,10086) order by id;")
print(f"total {len(rows)}")
for r in rows:
    d, op, hx, ts = r.split("|")
    b = bytes.fromhex(hx)
    if len(b) >= 16:
        qid = struct.unpack_from("<I", b, 12)[0]
        if qid < 1518 or qid > 1530: continue
    else:
        qid = struct.unpack_from("<I", b, 8)[0]
        if qid < 1518 or qid > 1530: continue
    body = " ".join(f"{struct.unpack_from('<I', b, o)[0]:08X}" for o in range(4, min(len(b), 48), 4))
    print(f"{ts} {d} op={op} len={len(b):>3} : {body}")
