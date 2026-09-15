import re, hashlib, pathlib, struct
helper = pathlib.Path("tools/client_patch_helpers/AvatarPreload.Patch.ps1").read_text(encoding="utf-8", errors="replace")
def lit(name):
    m = re.search(r"\$" + name + r"\s*=\s*Convert-HexBytes\s+'([0-9A-Fa-f ]+)'", helper)
    if m: return bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", m.group(1)))
    m = re.search(r"\$" + name + r"\s*=\s*Convert-HexBytes\s+@'\r?\n(.*?)\r?\n'@", helper, re.S)
    if m: return bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", m.group(1)))
    m = re.search(r"\$" + name + r"\s*=\s*Convert-HexBytes\s+@\"\r?\n(.*?)\r?\n\"@", helper, re.S)
    if m: return bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", m.group(1)))
    raise SystemExit("literal not found: " + name)
def num(name):
    m = re.search(r"\$" + name + r"\s*=\s*0x([0-9A-Fa-f]+)", helper)
    if not m: raise SystemExit("offset not found: " + name)
    return int(m.group(1), 16)
parts = {
    "preloadHook":  (num("preloadHookOffset"),  lit("patchedPreloadHook")),
    "preloadCave":  (num("preloadCaveOffset"),  lit("preloadCaveCode")),
    "timeoutHook":  (num("timeoutHookOffset"),  lit("patchedTimeoutHook")),
    "timeoutCave":  (num("timeoutCaveOffset"),  lit("patchedTimeoutCave")),
}
data = bytearray(pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes())
cur = hashlib.sha256(bytes(data)).hexdigest().upper()
print("当前哈希:", cur)
changes = 0
for name, (off, block) in parts.items():
    old = bytes(data[off:off+len(block)])
    diff = sum(1 for a, b in zip(old, block) if a != b)
    changes += diff
    print(f"  {name:<12} off=0x{off:X} len={len(block):<3} 变动={diff}")
    data[off:off+len(block)] = block
print("总变动字节:", changes, "（工具断言应为 206）")
after = hashlib.sha256(bytes(data)).hexdigest().upper()
print("预计打完后的哈希:", after)
pathlib.Path(".re/preload_after_hash.txt").write_text(after + "\n" + cur + "\n")
