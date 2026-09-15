import hashlib, pathlib
CLIENT = r"D:\Godswar Origin\Origin.exe"
b = pathlib.Path(CLIENT).read_bytes()
print("file:", CLIENT, len(b), "bytes")
print("sha256:", hashlib.sha256(b).hexdigest().upper())
sites = [
    ("lifecycle 0x4C14C5 (clear stale flag)", 0x0C14C5, "68045A9E00", "E9361E5000"),
    ("builder   0x5F4A82 (primary guard)",     0x1F4A82, "33FF33C9EB08", "E929E83C0090"),
    ("builder   0x5F05C2 (secondary guard)",   0x1F05C2, "8B44245033DB", "E9592D3D0090"),
]
for name, off, original, patched in sites:
    cur = b[off:off+len(bytes.fromhex(original))].hex().upper()
    state = "PATCHED (guard installed)" if cur == patched else ("ORIGINAL (no guard)" if cur == original else "UNKNOWN")
    print(f"{name}: file 0x{off:X} bytes={cur} -> {state}")
# V4 preload hooks
for name, off, original in [("V4 preload hook 0x4C14D6", 0x0C14D6, "68A0399500"), ("V4 timeout hook 0x5F58B6", 0x1F58B6, "8B0DA0605701")]:
    cur = b[off:off+len(bytes.fromhex(original))].hex().upper()
    print(f"{name}: {cur} -> {'V4 PRESENT' if cur != original else 'stock'}")
# cave emptiness
for name, off, size in [("lifecycle cave 0x9C3300", 0x5C3300, 17), ("primary cave 0x9C32B0", 0x5C32B0, 68), ("secondary cave 0x9C3320", 0x5C3320, 70)]:
    seg = b[off:off+size]
    print(f"{name}: {'used (non-zero)' if any(seg) else 'empty'} {seg[:16].hex().upper()}")
