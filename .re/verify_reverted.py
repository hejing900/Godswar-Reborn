import hashlib, pathlib
b = pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes()
print("当前 SHA256:", hashlib.sha256(b).hexdigest().upper())
print("（应等于装 V4 之前的 9D8E984F163AD838A2B19E27C6585B0E2E96AEEF2CCBB1AD76967B7376E57322）")
for name, off, n, expect in [
    ("V4 preload 钩子 0xC14D6（应恢复原字节 68 A0 39 95 00）", 0x0C14D6, 5, "68A0399500"),
    ("V4 timeout 钩子 0x1F58B6（应恢复 8B 0D A0 60 57 01）", 0x1F58B6, 6, "8B0DA0605701"),
    ("基础守卫 生命周期 0xC14C5（应仍在）", 0x0C14C5, 5, "E9361E5000"),
    ("基础守卫 主建模 0x1F4A82（应仍在）", 0x1F4A82, 6, "E929E83C0090"),
    ("基础守卫 第二建模 0x1F05C2（应仍在）", 0x1F05C2, 6, "E9592D3D0090"),
    ("QuestView 帧守卫 0x1DA4C0（应仍在）", 0x1DA4C0, 5, None),
]:
    cur = b[off:off+n].hex().upper()
    verdict = "" if expect is None else ("✓" if cur == expect else "✗ 期望 " + expect)
    print(f"  {name}: {cur} {verdict}")
print("  V4 preload 洞 0x5C3366（应全 0）:", b[0x5C3366:0x5C3366+16].hex().upper())
print("  V4 timeout 洞 0x5C341F（应全 0）:", b[0x5C341F:0x5C341F+16].hex().upper())
