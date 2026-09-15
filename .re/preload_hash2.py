import re, hashlib, pathlib
h = pathlib.Path("tools/client_patch_helpers/AvatarPreload.Patch.ps1").read_text(encoding="utf-8", errors="replace")
def lit(name):
    for pat in (r"\$" + name + r"\s*=\s*Convert-HexBytes\s+'([0-9A-Fa-f ]+)'",
                r"\$" + name + r"\s*=\s*Convert-HexBytes\s+@'\r?\n(.*?)\r?\n'@"):
        m = re.search(pat, h, re.S)
        if m: return bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", m.group(1)))
    raise SystemExit("missing " + name)
def num(name):
    m = re.search(r"\$" + name + r"\s*=\s*0x([0-9A-Fa-f]+)", h)
    if not m: raise SystemExit("missing offset " + name)
    return int(m.group(1), 16)
origPre, patPre = lit("originalPreloadHook"), lit("patchedPreloadHook")
preCode = lit("preloadCaveCode")
origT, patT = lit("originalTimeoutHook"), lit("patchedTimeoutHook")
tCode = lit("timeoutCaveCode")
offPre, offPreCave, offT, offTCave = num("preloadHookOffset"), num("preloadCaveOffset"), num("timeoutHookOffset"), num("timeoutCaveOffset")
data = bytearray(pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes())
cur = hashlib.sha256(bytes(data)).hexdigest().upper()
# mirror the Apply writes exactly
mut = 0
mut += sum(1 for a, b in zip(data[offPre:offPre+5], patPre) if a != b)
data[offPre:offPre+5] = patPre
mut += sum(1 for i, b in enumerate(preCode) if data[offPreCave+i] != b)
data[offPreCave:offPreCave+len(preCode)] = preCode
mut += sum(1 for a, b in zip(data[offT:offT+6], patT) if a != b)
data[offT:offT+6] = patT
mut += sum(1 for i, b in enumerate(tCode) if data[offTCave+i] != b)
data[offTCave:offTCave+len(tCode)] = tCode
after = hashlib.sha256(bytes(data)).hexdigest().upper()
print("当前哈希      :", cur)
print("预计完成后哈希:", after)
print("总变动字节    :", mut, "(工具断言 206)")
print("preload 钩子  :", patPre.hex().upper())
print("preload 洞代码:", preCode.hex().upper())
print("timeout 钩子  :", patT.hex().upper())
print("timeout 洞代码:", tCode.hex().upper())
pathlib.Path(".re/preload_hashes.txt").write_text(cur + "\n" + after + "\n")
