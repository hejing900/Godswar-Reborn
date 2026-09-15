import hashlib, pathlib
b = pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes()
print("当前 SHA256:", hashlib.sha256(b).hexdigest().upper())
checks = [
    ("头像守卫 生命周期 0xC14C5", 0x0C14C5, "E9361E5000"),
    ("头像守卫 主建模 0x1F4A82",  0x1F4A82, "E929E83C0090"),
    ("头像守卫 第二建模 0x1F05C2",0x1F05C2, "E9592D3D0090"),
    ("QuestView 帧守卫 0x1DA4C0", 0x1DA4C0, None),
    ("超时守卫 0x1F58B6",         0x1F58B6, "E964DB3C0090"),
]
for name, off, patched in checks:
    cur = b[off:off+6].hex().upper()
    if patched:
        print(f"  {name}: {cur} -> {'已装' if cur.startswith(patched[:len(patched)]) else '未装'}")
    else:
        print(f"  {name}: {cur}")
print("洞 0x5C32B0:", b[0x5C32B0:0x5C32B0+16].hex().upper())
print("洞 0x5C3300:", b[0x5C3300:0x5C3300+16].hex().upper())
print("洞 0x5C3320:", b[0x5C3320:0x5C3320+16].hex().upper())
