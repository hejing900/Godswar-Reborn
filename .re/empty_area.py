import re
text = open("src/Godswar.Server/Packets/PacketBuilder.QuestAnswerFrames.Generated.cs", encoding="utf-8-sig").read()
m = re.search(r"EmptyQuestRewardArea\s*=\s*Convert\.FromHexString\((.*?)\);", text, re.S)
hexblob = "".join(re.findall(r'"([0-9a-fA-F]*)"', m.group(1)))
b = bytes.fromhex(hexblob)
print("EmptyQuestRewardArea bytes:", len(b))
print("first 80:", b[:80].hex())
import struct
for i in range(4):
    off = 8 + i*72
    print(f"  slot{i} item={struct.unpack_from('<i', b, off)[0]} count={struct.unpack_from('<i', b, off+4)[0]}")
