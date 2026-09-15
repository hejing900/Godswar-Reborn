"""Diff the client's own NPC template blocks for the two camps' equivalents."""
import re
import sys

NPC_INI = r"D:\Godswar Origin\Localization\en_us\Settings\Sys\NPC.INI"

PAIRS = [
    ("Athens_094_Male30", "Sparta_094_Male30"),
    ("Athens_106_MaleHero2", "Sparta_106_MaleSage1"),
    ("Athens_095", None),
]


def sections():
    found = {}
    current = None
    raw = open(NPC_INI, "rb").read()
    if raw.startswith(b"\xff\xfe"):
        text = raw.decode("utf-16-le", errors="replace")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = raw.decode("latin-1", errors="replace")
    for line in text.splitlines():
        match = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if match:
            current = match.group(1)
            found[current] = []
            continue
        if current is not None:
            found[current].append(line.rstrip())
    return found


def main():
    table = sections()
    for left, right in PAIRS:
        if right is None:
            continue
        if left not in table or right not in table:
            print(f"{left} / {right}: missing "
                  f"({left in table}/{right in table})")
            continue
        a = [line for line in table[left] if line.strip()]
        b = [line for line in table[right] if line.strip()]
        print(f"--- {left} ({len(a)} fields) vs {right} ({len(b)} fields)")
        keys_a = {line.split("=")[0].strip().lower(): line.split("=", 1)[1].strip()
                  for line in a if "=" in line}
        keys_b = {line.split("=")[0].strip().lower(): line.split("=", 1)[1].strip()
                  for line in b if "=" in line}
        for key in sorted(set(keys_a) | set(keys_b)):
            va, vb = keys_a.get(key), keys_b.get(key)
            if va != vb:
                print(f"    {key}: Athens={va!r} Sparta={vb!r}")
        extra_a = [line for line in a if "=" not in line]
        extra_b = [line for line in b if "=" not in line]
        if extra_a or extra_b:
            print(f"    non-key lines: Athens={extra_a} Sparta={extra_b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
