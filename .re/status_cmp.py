import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
rows = q("select coalesce(opcode,0), encode(clear_bytes,'hex'), captured_at from packet_transactions where captured_at between '2026-09-14 01:05' and '2026-09-14 01:16' and opcode in (10166,10086) order by id;")
print(f"{len(rows)} rows")
for r in rows:
    op, hx, ts = r.split("|"); op = int(op); b = bytes.fromhex(hx)
    if op == 10166 and len(b) > 200:
        print(f"{ts} 10166 len={len(b)} w60={struct.unpack_from('<I',b,60)[0]} w96={struct.unpack_from('<I',b,96)[0]} w100={struct.unpack_from('<I',b,100)[0]} w104={struct.unpack_from('<I',b,104)[0]} w120={struct.unpack_from('<I',b,120)[0]} w124={struct.unpack_from('<I',b,124)[0]} w228={struct.unpack_from('<I',b,228)[0]}")
    elif op == 10086:
        print(f"{ts} 10086 quest={struct.unpack_from('<I',b,12)[0]} idx={struct.unpack_from('<I',b,16)[0]:08X} +28={struct.unpack_from('<I',b,28)[0]} +36={struct.unpack_from('<I',b,36)[0]}")
