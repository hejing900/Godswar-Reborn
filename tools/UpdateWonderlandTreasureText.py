"""Apply the captured Fane reward dialogue with this server's four-gem reward."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VALUES = {
    'FANE_NMGV_T125': 'Sapphire IV*',
    'FANE_NMGV_T126': 'Emerald IV*',
    'FANE_NMGV_T127': '',
    'FANE_NMGV_T150': 'Your treasure is not ready yet. Please try again shortly.',
}


def transform(path: Path, data: bytes) -> bytes:
    text = data.decode('utf-8-sig')
    newline = '\r\n' if '\r\n' in text else '\n'
    if path.name == 'LuaText.lua':
        for key, value in VALUES.items():
            pattern = r'(?m)^LuaText\.' + key + r'\s*=\s*"[^\r\n]*"[^\r\n]*'
            replacement = f'LuaText.{key} = "{value}"'
            matches = list(re.finditer(pattern, text))
            if len(matches) > 1 or (not matches and key != 'FANE_NMGV_T150'):
                raise ValueError(f'Expected unique {key} in {path}')
            text = re.sub(pattern, lambda _: replacement, text) if matches else text.rstrip('\r\n') + newline + replacement + newline
    else:
        before = 'elseif SubID == 141 or SubID == 142 then'
        after = 'elseif SubID == 141 or SubID == 142 or SubID == 150 then'
        if text.count(before) + text.count(after) != 1:
            raise ValueError(f'Expected Fane terminal-result branch in {path}')
        text = text.replace(before, after)
    encoded = text.encode('utf-8')
    return (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-root', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    changes = []
    prepared = []
    for locale in ('en_us', 'zh_cn'):
        for relative in ('UI/Base/LuaText.lua', 'UI/XML/NpcFun/NpcFunFane.lua'):
            path = args.client_root / 'Localization' / locale / relative
            before = path.read_bytes()
            after = transform(path, before)
            assert transform(path, after) == after, 'Patch must be idempotent'
            changes.append({'path': str(path), 'before': hashlib.sha256(before).hexdigest(),
                            'after': hashlib.sha256(after).hexdigest(), 'changed': before != after})
            prepared.append((path, path.relative_to(args.client_root), before, after))
    if args.apply:
        # Validate all inputs before any mutation, and retain the exact original bytes.
        for path, relative, before, after in prepared:
            if before == after:
                continue
            backup = args.backup / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists() and backup.read_bytes() != before:
                raise ValueError(f'Refusing to overwrite a different backup: {backup}')
            backup.write_bytes(before)
        for path, relative, before, after in prepared:
            if before == after:
                continue
            path.write_bytes(after)
            assert path.read_bytes() == after
    print(json.dumps({'applied': args.apply, 'files': changes}, indent=2))


if __name__ == '__main__':
    main()
