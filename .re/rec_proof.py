import subprocess, struct, re
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]
pages, answers = {}, {}
for r in q("select opcode, encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode in (10090,10082) order by id;"):
    op, hx = r.split("|"); b = bytes.fromhex(hx)
    if op == "10090": pages.setdefault(struct.unpack_from('<I', b, 8)[0], b)
    else:
        qid = struct.unpack_from('<I', b, 12)[0]; kind = struct.unpack_from('<I', b, 20)[0]
        answers.setdefault((qid, kind), b)
for qid in (518, 519, 520, 1522):
    page = pages.get(qid)
    if not page: continue
    rec = page[104:176]
    matches = [k for k, b in answers.items() if b[64:136] == rec]
    print(f"quest {qid}: page record == answer area[0:72] of {matches}")
    if not matches:
        print("   rec:", rec[:40].hex())
        for k, b in answers.items():
            if k[0] == qid: print(f"   ans{k}:", b[64:104].hex())
