import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:400]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
rows = q("select direction, opcode, encode(clear_bytes,'hex'), captured_at from packet_transactions where opcode in (10084,10086) and captured_at > '2026-09-13' order by id;")
print(f"{len(rows)} rows")
for r in rows[:60]:
    d, op, hx, ts = r.split("|")
    b = bytes.fromhex(hx)
    body = " ".join(f"{struct.unpack_from('<I', b, o)[0]:08X}" for o in range(4, min(len(b), 48), 4))
    print(f"{ts} {d} op={op} len={len(b):>3} : {body}")
