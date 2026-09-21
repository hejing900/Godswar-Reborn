#!/usr/bin/env python3
"""Hermetic title-display patch, native ABI/width, and transaction checks."""
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch

import PatchClientTitleBrackets as subject
from client_patch_helpers import title_bracket_colors as native
from holy_suit_tiers.text import PatchError
from title_bracket_checks import execute_formatter


class TitleDisplayChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="reborn-title-display-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        data = bytearray(6676480)
        data[:2] = b"MZ"
        struct.pack_into('<I', data, 0x3C, 0x80)
        data[0x80:0x84] = b'PE\0\0'
        struct.pack_into('<HH', data, 0x84, 0x14C, 1)
        struct.pack_into('<H', data, 0x94, 0xE0)
        struct.pack_into('<H', data, 0x98, 0x10B)
        struct.pack_into('<I', data, 0xB4, 0x400000)
        data[0x178:0x180] = b'.rdata\0\0'
        struct.pack_into('<III', data, 0x184, 0x51C000, 0xA8000, 0x51C000)
        struct.pack_into('<I', data, 0x19C, 0x60000040)
        data[subject.FORMAT_OFFSET:subject.FORMAT_OFFSET + 15] = subject.LEGACY_FORMAT
        data[subject.WIDTH_OFFSET:subject.WIDTH_OFFSET + 15] = subject.LEGACY_WIDTH
        for offset, value in subject.REQUIRED.items():
            data[offset:offset + len(value)] = value
        for offset in subject.HOOKS:
            data[offset:offset + 5] = subject.relative_call(offset, 0x420921)
        for pin in native.PROFILE['required_pins']:
            offset, value = int(pin['offset'], 16), bytes.fromhex(pin['hex'])
            data[offset:offset + len(value)] = value
        (self.root / "Origin.exe").write_bytes(data)
        for locale in ("en_us", "zh_cn"):
            directory = self.root / "Localization" / locale / "Text"
            directory.mkdir(parents=True)
            rows = ["99\tOrdinary", "5155\t|cff4FD17BGatebreaker|cFFFFFFFF"]
            for identity, color in subject.COLORS.items():
                name = f"Medusa {identity}" if locale == "en_us" else f"美杜莎 {identity}"
                rows.append(f"{identity}\t|cff{color}[{name}]|cFFFFFFFF")
            (directory / "DesigName.dat").write_bytes(("\r\n".join(rows) + "\r\n").encode("utf-16"))
            (directory / "DesigInfo.dat").write_bytes("99\tUnchanged description\r\n".encode("utf-16"))

    def test_native_formatter_and_width_separate_display_from_list(self):
        plan = subject.build_plan(self.root)
        code = plan[0].after
        # The actual x86 wrapper is executed below with an original formatter stub.
        entry = 0x20921
        self.assertEqual(0xE9, code[entry])
        target = 0x400000 + entry + 5 + struct.unpack_from("<i", code, entry + 1)[0]
        self.assertEqual(0x9C3F20, target)
        self.assertEqual(bytes.fromhex("CCCCCCCCCCCCCCCCCCCC"), code[entry + 5:entry + 15])
        changed = {index for index, pair in enumerate(zip(plan[0].before, code)) if pair[0] != pair[1]}
        self.assertTrue(changed <= set(range(0x20921, 0x20930)) | set(range(0x5C3F20, 0x5C3FA0)))
        for item in plan[1:]:
            if item.path.name == "DesigInfo.dat":
                self.assertEqual(item.before, item.after)
                continue
            before = dict(line.split("\t", 1) for line in item.before.decode("utf-16").splitlines())
            after = dict(line.split("\t", 1) for line in item.after.decode("utf-16").splitlines())
            for identity, list_name in after.items():
                # Native selection getter42BCF0 supplies this raw catalog name.
                self.assertNotIn("[", list_name)
                self.assertNotIn("]", list_name)
                display_bytes, length, calls = execute_formatter(code, list_name.encode('utf-8'))
                display = display_bytes.decode('utf-8')
                self.assertEqual(1, calls)
                self.assertEqual(len(display_bytes), length)
                if list_name.startswith('|c'):
                    self.assertEqual(list_name[:10] + '[' + list_name[10:-10] + ']' + list_name[-10:], display)
                else:
                    self.assertEqual('[' + list_name + ']', display)
                visible = re.sub(r"\|c[0-9a-fA-F]{8}", "", display)
                self.assertTrue(visible.startswith("[") and visible.endswith("]"))
                if identity in ("99", "5155"):
                    self.assertEqual(before[identity], list_name)
                if list_name.isascii():
                    self.assertEqual(len(visible) * 8, execute_width(code, display))

    def test_v1_upgrade_changes_only_executable_and_preserves_plain_catalogs(self):
        old = (self.root / 'Origin.exe').read_bytes()
        plan = subject.build_plan(self.root)
        for item in plan[1:]:
            item.path.write_bytes(item.after)
        v1 = bytearray(old)
        v1[subject.FORMAT_OFFSET:subject.FORMAT_OFFSET + 15] = subject.DISPLAY_FORMAT
        v1[subject.WIDTH_OFFSET:subject.WIDTH_OFFSET + 15] = subject.DISPLAY_WIDTH
        plan[0].path.write_bytes(v1)
        self.assertEqual(0, subject.legacy_guard(self.root))
        upgrade = subject.build_plan(self.root)
        self.assertEqual([True, False, False, False, False], [item.changed for item in upgrade])
        self.assertEqual('ColoredBrackets', subject.executable_state(upgrade[0].after))

    def test_actual_wrapper_leaves_ordinary_truncated_and_incomplete_spans_stock(self):
        code = subject.build_plan(self.root)[0].after
        for name in (b'Plain', b'|cffA335EEMissing reset', b'|xffA335EEName|cFFFFFFFF',
                     b'|cffA335EEName|cFFFF0000', b'x' * 80):
            output, length, calls = execute_formatter(code, name)
            self.assertEqual((b'[' + name + b']')[:64], output)
            self.assertEqual(1, calls)
        colored = b'|cffA335EEName|cFFFFFFFF'
        output, length, _ = execute_formatter(code, colored, forced_result=-1)
        self.assertEqual(b'[' + colored + b']', output)
        self.assertEqual(0xFFFFFFFF, length)

    def test_active_retired_hook_and_foreign_cave_owner_reject(self):
        path = self.root / 'Origin.exe'
        original = path.read_bytes()
        for offset, value in ((0x1B5B97, bytes.fromhex('E984E34000')),
                              (0x5C3F20, b'\x90'),
                              (0x2000, subject.relative_call(0x2000, 0x9C3F20))):
            changed = bytearray(original)
            changed[offset:offset + len(value)] = value
            path.write_bytes(changed)
            with self.assertRaises(PatchError):
                subject.build_plan(self.root)
        path.write_bytes(original)

    def test_install_backup_idempotence_and_legacy_guard(self):
        self.assertEqual(2, subject.legacy_guard(self.root))
        plan = subject.build_plan(self.root)
        with patch.object(subject, "assert_client_closed") as closed:
            result = subject.install(self.root, plan)
            self.assertEqual(2, closed.call_count)
        self.assertEqual(3, result["files_changed"])
        manifest = Path(result["backup_manifest"])
        metadata = json.loads(manifest.read_text())
        self.assertEqual("Verified", metadata["status"])
        for item in plan:
            self.assertEqual(item.before, (manifest.parent / item.path.relative_to(self.root)).read_bytes())
            self.assertEqual(item.after, item.path.read_bytes())
        self.assertEqual(0, subject.legacy_guard(self.root))
        repeat = subject.build_plan(self.root)
        self.assertFalse(any(item.changed for item in repeat))
        self.assertEqual("AlreadyMatches", subject.install(self.root, repeat)["status"])

    def test_client_open_rejects_before_backup_or_write(self):
        plan = subject.build_plan(self.root)
        with patch.object(subject, "assert_client_closed", side_effect=PatchError("client open")):
            with self.assertRaisesRegex(PatchError, "client open"):
                subject.install(self.root, plan)
        self.assertFalse((self.root / "backups").exists())
        self.assertTrue(all(item.path.read_bytes() == item.before for item in plan))

    def test_partial_native_and_catalog_states_reject(self):
        origin = self.root / "Origin.exe"
        initial = origin.read_bytes()
        broken = bytearray(initial)
        broken[subject.FORMAT_OFFSET:subject.FORMAT_OFFSET + 15] = subject.DISPLAY_FORMAT
        origin.write_bytes(broken)
        with self.assertRaisesRegex(PatchError, "partial"):
            subject.build_plan(self.root)
        with self.assertRaises(PatchError):
            subject.legacy_guard(self.root)
        origin.write_bytes(initial)
        names = self.root / "Localization/en_us/Text/DesigName.dat"
        names.write_bytes(names.read_bytes().decode("utf-16").replace("[Medusa 5009]", "Medusa 5009").encode("utf-16"))
        with self.assertRaisesRegex(PatchError, "different patch states"):
            subject.build_plan(self.root)

    def test_unknown_hook_and_duplicate_title_reject(self):
        origin = self.root / "Origin.exe"
        data = bytearray(origin.read_bytes())
        data[0x21185] ^= 1
        origin.write_bytes(data)
        with self.assertRaisesRegex(PatchError, "hook differs"):
            subject.build_plan(self.root)
        data[0x21185] ^= 1
        origin.write_bytes(data)
        names = self.root / "Localization/en_us/Text/DesigName.dat"
        names.write_bytes((names.read_bytes().decode("utf-16") + "5009\tDuplicate\r\n").encode("utf-16"))
        with self.assertRaisesRegex(PatchError, "unique"):
            subject.build_plan(self.root)

    def test_failed_second_file_rolls_back_executable(self):
        plan = subject.build_plan(self.root)
        original_write = subject.atomic_write
        failed = False

        def fail_second(path, content):
            nonlocal failed
            if path == plan[1].path and not failed:
                failed = True
                raise OSError("injected replace failure")
            original_write(path, content)

        with patch.object(subject, "assert_client_closed"), patch.object(subject, "atomic_write", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "injected"):
                subject.install(self.root, plan)
        self.assertTrue(all(item.path.read_bytes() == item.before for item in plan))
        metadata = json.loads(next((self.root / "backups").rglob("manifest.json")).read_text())
        self.assertEqual("RolledBack", metadata["status"])


def execute_width(code: bytes, display: str) -> int:
    """Execute the audited width helper's small x86 instruction subset."""
    pc, ecx, esi, zero = 0x21BD1, 0, len(display), False
    # EDI is the actor; the formatted title begins at its +9A1.
    memory = b"\0" * 0x9A1 + display.encode("ascii") + b"\0"
    for _ in range(12):
        instruction = code[pc:pc + 9]
        if instruction.startswith(b"\x89\xf1"):
            ecx, pc = esi, pc + 2
        elif instruction.startswith(b"\x80\xbf"):
            offset = struct.unpack_from("<I", instruction, 2)[0]
            zero, pc = memory[offset] == instruction[6], pc + 7
        elif instruction[0] in (0x74, 0xEB):
            take = instruction[0] == 0xEB or zero
            pc += 2 + (struct.unpack("b", instruction[1:2])[0] if take else 0)
        elif instruction.startswith(b"\x83\xe9"):
            ecx, pc = ecx - instruction[2], pc + 3
        elif instruction.startswith(b"\xc1\xe1"):
            ecx, pc = ecx << instruction[2], pc + 3
        elif instruction[0] == 0xC3:
            return ecx
        else:
            raise AssertionError(f"Unexpected native width instruction at{pc:x}")
    raise AssertionError("Native width helper did not return")


if __name__ == "__main__":
    unittest.main()
