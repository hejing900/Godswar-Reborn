import re, struct, sys
path = "src/Godswar.Server/Packets/PacketBuilder.QuestHandInFrames.Generated.cs"
text = open(path, encoding="utf-8-sig").read()
# first dictionary block = hand-in acks
blocks = re.findall(r"private static readonly Dictionary<uint, string> (\w+) = new\(\)\s*\{(.*?)\n    \};", text, re.S)
for name, body in blocks:
    entries = re.findall(r"\[(\d+)u\]\s*=\s*((?:\s*\"[0-9a-fA-F]*\"\s*\+?)+)", body)
    print(f"### {name}: {len(entries)} entries")
    if name != "CapturedHandInAcks":
        continue
    for qid, hexblob in entries:
        h = "".join(re.findall(r"\"([0-9a-fA-F]*)\"", hexblob))
        b = bytes.fromhex(h)
        g = [struct.unpack_from("<I", b, o)[0] for o in range(0, len(b), 4)]
        print(f"  quest {qid:>4} len={len(b):>3} : " + " ".join(f"{v:08X}" for v in g))
