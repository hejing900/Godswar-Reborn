import subprocess, struct
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
def q(sql):
    r = subprocess.run(PSQL+[sql], capture_output=True, text=True)
    if r.returncode: print(r.stderr[:300]); raise SystemExit(1)
    return [l for l in r.stdout.splitlines() if l.strip()]
pages = {}
for r in q("select encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode=10090 order by id;"):
    b = bytes.fromhex(r)
    pages.setdefault(b, 0)
    pages[b] += 1
print(f"{len(pages)} distinct reference 10090 pages")
for b, n in pages.items():
    qid = struct.unpack_from('<I', b, 8)[0]
    print(f"x{n} len={len(b)} count@4={struct.unpack_from('<I',b,4)[0]} quest@8={qid}")
    print("   " + " ".join(f"+{o}:{struct.unpack_from('<I',b,o)[0]:08X}" for o in range(4, 132, 4)))
