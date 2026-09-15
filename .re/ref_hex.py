import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
for r in q("select opcode, encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode in (10076,10086) order by id;"):
    op, hx = r.split("|"); b = bytes.fromhex(hx); op = int(op)
    qid = struct.unpack_from('<I', b, 8)[0]
    print(f"op={op} quest={qid} len={len(b)}")
    print("   ", hx)
