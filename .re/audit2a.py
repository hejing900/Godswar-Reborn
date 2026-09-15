import pathlib, re
IMAGE = pathlib.Path(r"D:\Godswar Origin\Origin.exe").read_bytes()
RDATA_RAW_START, RDATA_VA, RDATA_VSIZE = 0x51C000, 0x91C000, 0xA7090
def va(off):
    return RDATA_VA + (off - RDATA_RAW_START) if off >= RDATA_RAW_START else 0x400000 + off - 0x1000
def needed_section_fix(off, size=1):
    # anything in .rdata virtual range beyond current vsize, or in .rdata at all (needs EXEC), or in the hole
    if 0x51C000 <= off < 0x5C4000:
        v = va(off)
        if v >= RDATA_VA + RDATA_VSIZE:  # unmapped hole
            return "CAVE-UNMAPPED"
        return "SECT-NOEXEC"
    return ""
scripts = sorted(pathlib.Path("tools").glob("PatchClient*.ps1"))
pat_hex = re.compile(r"\$(\w+)\s*=\s*Convert-HexBytes\s+'([0-9A-Fa-f ]+)'")
pat_here = re.compile(r"\$(\w+)\s*=\s*Convert-HexBytes\s+@'\r?\n(.*?)\r?\n'@", re.S)
def norm(t):
    try: return bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", t))
    except ValueError: return b""
rows = []
for s in scripts:
    text = s.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"ValidateSet\([^)]*Status", text):
        continue
    helpers = re.findall(r"Join-Path\s+\$helperRoot\s+'([^']+)'", text) + re.findall(r"\$PSScriptRoot\\?([\w.]+\.ps1)", text)
    for h in helpers:
        p = pathlib.Path("tools/client_patch_helpers")/h
        if p.exists(): text += "\n" + p.read_text(encoding="utf-8", errors="replace")
    lits = [(n, norm(b)) for n, b in pat_hex.findall(text)] + [(n, norm(b)) for n, b in pat_here.findall(text)]
    lits = [(n, b) for n, b in lits if 3 <= len(b) <= 40]
    orig = [(n, b) for n, b in lits if "origin" in n.lower()]
    patched = [(n, b) for n, b in lits if "patch" in n.lower()]
    offs = [int(x, 16) for x in re.findall(r"\$\w*(?:[Cc]ave|[Hh]ook|Continuation|Epilogue|Fault)\w*Offset\w*\s*=\s*0x([0-9A-Fa-f]+)", text)]
    offs += [int(x, 16) for x in re.findall(r"(?:Cave|Hook)Offset\s*=\s*0x([0-9A-Fa-f]+)", text)]
    fixes = sorted({needed_section_fix(o) for o in offs if needed_section_fix(o)})
    hashes = len(set(re.findall(r"\b[0-9A-F]{64}\b", text)))
    orig_missing = [n for n, b in orig if IMAGE.count(b) == 0]
    already = [n for n, b in patched if IMAGE.count(b) > 0]
    verdict = []
    if orig_missing: verdict.append("PRED-MISMATCH")
    if already: verdict.append("PARTIAL?")
    if hashes: verdict.append(f"HASHGATES:{hashes}")
    if not verdict: verdict.append("PRED-OK")
    rows.append((s.name, ",".join(fixes) or "no-cave", " / ".join(verdict), len(orig), len(patched)))
print(f"{'script':<50}{'cave-need':<24}{'verdict'}")
for name, fix, verdict, no, np_ in rows:
    print(f"{name:<50}{fix:<24}{verdict}")
print(f"\n共 {len(rows)} 个带 Status 的补丁脚本")

