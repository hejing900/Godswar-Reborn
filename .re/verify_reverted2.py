import hashlib, pathlib
b = pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes()
print("sha256:", hashlib.sha256(b).hexdigest().upper())
checks = [
    ("v4 preload hook   0xC14D6", 0x0C14D6, 5, "68A0399500"),
    ("v4 timeout hook   0x1F58B6", 0x1F58B6, 6, "8B0DA0605701"),
    ("base guard lifecyc 0xC14C5", 0x0C14C5, 5, "E9361E5000"),
    ("base guard primary 0x1F4A82", 0x1F4A82, 6, "E929E83C0090"),
    ("base guard second  0x1F05C2", 0x1F05C2, 6, "E9592D3D0090"),
]
for name, off, n, expect in checks:
    cur = b[off:off+n].hex().upper()
    print(f"  {name}: {cur} {'OK' if cur == expect else 'MISMATCH expected ' + expect}")
print("  v4 preload cave 0x5C3366:", b[0x5C3366:0x5C3366+16].hex().upper())
print("  v4 timeout cave 0x5C341F:", b[0x5C341F:0x5C341F+16].hex().upper())
print("  questview hook  0x1DA4C0:", b[0x1DA4C0:0x1DA4C0+5].hex().upper())
