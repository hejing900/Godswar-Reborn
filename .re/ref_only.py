import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
rows = q("select opcode, encode(clear_bytes,'hex'), captured_at from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode in (10076,10082,10086,10087,10090) order by id;")
print(f"{len(rows)} reference frames (port 13333)")
for r in rows:
    op, hx, ts = r.split("|"); op = int(op); b = bytes.fromhex(hx)
    if op == 10076:
        print(f"{ts} 10076 len={len(b)} giver={struct.unpack_from('<I',b,12)[0]} quest={struct.unpack_from('<I',b,16)[0]} kind={struct.unpack_from('<I',b,20)[0]} monster={struct.unpack_from('<I',b,36)[0]} required={struct.unpack_from('<I',b,48)[0]}")
    elif op == 10082:
        qid = struct.unpack_from('<I',b,12)[0]
        sl = [struct.unpack_from('<i',b,72+i*72)[0] for i in range(4)]
        sl2 = [struct.unpack_from('<i',b,360+i*72)[0] for i in range(4)]
        print(f"{ts} 10082 len={len(b)} quest={qid} kind={struct.unpack_from('<I',b,20)[0]} monster={struct.unpack_from('<I',b,36)[0]} req={struct.unpack_from('<I',b,48)[0]} area1={sl} area2={sl2}")
    elif op == 10086:
        print(f"{ts} 10086 len={len(b)} giver={struct.unpack_from('<I',b,4)[0]} resp={struct.unpack_from('<I',b,8)[0]} quest={struct.unpack_from('<I',b,12)[0]} idx={struct.unpack_from('<I',b,16)[0]:08X} exp={struct.unpack_from('<I',b,28)[0]} tp={struct.unpack_from('<I',b,36)[0]}")
    elif op == 10090:
        print(f"{ts} 10090 len={len(b)} first={b[:24].hex()}")
    else:
        print(f"{ts} {op} len={len(b)} {b[:32].hex()}")
