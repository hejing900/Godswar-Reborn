import pathlib, re, collections
CLIENT = pathlib.Path(r"D:\Godswar Origin\Origin.exe")
image = CLIENT.read_bytes()
root = pathlib.Path("tools")
scripts = sorted(list(root.glob("PatchClient*.ps1")) + list(root.glob("client_patch_helpers/*.Patch.ps1")) + list(root.glob("client_patch_helpers/*.Core.ps1")))
pat_hex = re.compile(r"\$(\w+)\s*=\s*Convert-HexBytes\s+'([0-9A-Fa-f ]+)'")
pat_here = re.compile(r"\$(\w+)\s*=\s*Convert-HexBytes\s+@'\r?\n(.*?)\r?\n'@", re.S)
def norm(t):
    return bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", t))
rows = []
for s in scripts:
    text = s.read_text(encoding="utf-8", errors="replace")
    lits = []
    for name, blob in pat_hex.findall(text):
        try: lits.append((name, norm(blob)))
        except ValueError: pass
    for name, blob in pat_here.findall(text):
        try: lits.append((name, norm(blob)))
        except ValueError: pass
    patched = [(n, b) for n, b in lits if "patch" in n.lower() and 3 <= len(b) <= 40]
    original = [(n, b) for n, b in lits if "origin" in n.lower() and 3 <= len(b) <= 40]
    if not patched:
        continue
    def found(b):
        return image.count(b)
    p_found = sum(1 for _, b in patched if found(b) > 0)
    o_found = sum(1 for _, b in original if found(b) > 0)
    rows.append((s.name, len(patched), p_found, len(original), o_found))
print(f"{'script':<52}{'patched found/total':>22}{'original found/total':>23}")
for name, pt, pf, ot, of in rows:
    flag = ""
    if pf == 0: flag = "  <== 未安装"
    elif pf < pt: flag = "  <== 部分安装?"
    print(f"{name:<52}{f'{pf}/{pt}':>22}{f'{of}/{ot}':>23}{flag}")
