import hashlib, pathlib
p = pathlib.Path(r"D:\Godswar Origin\Origin.exe"); b = p.read_bytes()
print("当前 SHA256:", hashlib.sha256(b).hexdigest().upper(), f"({len(b)} 字节)")
for name, off, n in [("V4 preload 钩子 0xC14D6", 0x0C14D6, 5), ("V4 timeout 钩子 0x1F58B6", 0x1F58B6, 6),
                     ("基础守卫 生命周期 0xC14C5", 0x0C14C5, 5), ("基础守卫 主建模 0x1F4A82", 0x1F4A82, 6),
                     ("QuestView 帧守卫 0x1DA4C0", 0x1DA4C0, 5)]:
    print(f"  {name}: {b[off:off+n].hex().upper()}")
print("  V4 preload 洞 0x5C3366:", b[0x5C3366:0x5C3366+16].hex().upper())
print("  V4 timeout 洞 0x5C341F:", b[0x5C341F:0x5C341F+16].hex().upper())
