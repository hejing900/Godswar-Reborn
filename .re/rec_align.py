import subprocess, struct, re
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]
pages = {}
for r in q("select encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode=10090 order by id;"):
    b = bytes.fromhex(r); pages[struct.unpack_from('<I', b, 8)[0]] = b
for qid in (518, 1522, 520):
    b = pages.get(qid)
    if not b: continue
    print(f"== reference page quest {qid}: record area 100..200")
    for o in range(100, 200, 4):
        print(f"   +{o}:{struct.unpack_from('<I',b,o)[0]:08X}", end="")
        if (o-100) % 24 == 20: print()
    print()
# our own generated records table
text = open("src/Godswar.Server/Domain/World/Content/StarterQuestRewardRecords.cs", encoding="utf-8-sig").read()
for m in re.finditer(r"\[(\d+)u\]\s*=\s*Convert\.FromHexString\((.*?)\)", text, re.S):
    qid = int(m.group(1)); hx = "".join(re.findall(r'"([0-9a-fA-F]*)"', m.group(2)))
    b = bytes.fromhex(hx)
    print(f"StarterQuestRewardRecords[{qid}] len={len(b)} first16={b[:16].hex()} item@8={struct.unpack_from('<I',b,8)[0]} item@0={struct.unpack_from('<I',b,0)[0]}")
