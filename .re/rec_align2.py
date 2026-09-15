import subprocess, struct, re
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]
pages = {}
for r in q("select encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode=10090 order by id;"):
    b = bytes.fromhex(r); pages.setdefault(struct.unpack_from('<I', b, 8)[0], b)
def rows(b, start, end, label):
    print(f"-- {label}")
    for o in range(start, end, 4):
        print(f"   +{o}={struct.unpack_from('<I',b,o)[0]:08X}", end="")
        if (o - start) % 20 == 16: print()
    print()
for qid in (518, 519, 520, 1522):
    if qid in pages:
        rows(pages[qid], 104, 184, f"reference page quest {qid} (104..184)")
text = open("src/Godswar.Server/Domain/World/Content/StarterQuestRewardRecords.cs", encoding="utf-8-sig").read()
for m in re.finditer(r"\[(\d+)u\]\s*=\s*Convert\.FromHexString\((.*?)\)", text, re.S):
    qid = int(m.group(1)); hx = "".join(re.findall(r'"([0-9a-fA-F]*)"', m.group(2))); b = bytes.fromhex(hx)
    rows(b, 0, 40, f"our StarterQuestRewardRecords[{qid}] (0..40)")
ans = open("src/Godswar.Server/Packets/PacketBuilder.QuestAnswerFrames.Generated.cs", encoding="utf-8-sig").read()
m = re.search(r"EmptyQuestRewardArea\s*=\s*Convert\.FromHexString\((.*?)\);", ans, re.S)
b = bytes.fromhex("".join(re.findall(r'"([0-9a-fA-F]*)"', m.group(1))))
rows(b, 0, 40, "our EmptyQuestRewardArea (0..40)")
