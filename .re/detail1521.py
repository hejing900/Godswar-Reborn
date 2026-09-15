import subprocess
PSQL = ["docker","exec","godswar-postgres","psql","-U","godswar","-d","godswar","-t","-A","-F","|","-c"]
r = subprocess.run(PSQL+["select encode(clear_bytes,'hex') from packet_transactions where direction='S2C' and split_part(source_endpoint,':',2)='13333' and opcode=10076 and encode(clear_bytes,'hex') like '%f1050000%' order by id limit 1;"], capture_output=True, text=True, check=True)
h = r.stdout.strip()
print(len(h)//2, "bytes")
for i in range(0, len(h), 128):
    print('            "' + h[i:i+128] + '"' + (' +' if i+128 < len(h) else ''))
