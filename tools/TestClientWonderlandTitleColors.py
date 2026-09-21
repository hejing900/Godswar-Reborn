#!/usr/bin/env python3
"""Hermetic ownership, native markup and transaction checks for title colors."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import PatchClientWonderlandTitleColors as subject
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import atomic_write, digest

# Independently authored expected native markup; the visible names gain no
# brackets, suffixes or statistic text when the native color tags are stripped.
EXPECTED = {
    5155: "|cff4FD17BGatebreaker|cFFFFFFFF",
    5114: "|cff4AA8FFDemonbreaker|cFFFFFFFF",
    5156: "|cff56C5FFFlamebreaker|cFFFFFFFF",
    5115: "|cffA875FFStonebreaker|cFFFFFFFF",
    5157: "|cffCB7CFFMarshal's Bane|cFFFFFFFF",
    5116: "|cffFF9F32Dragonbane|cFFFFFFFF",
    5117: "|cffF45D76Hydra's Bane|cFFFFFFFF",
    5118: "|cffFFE49AWonderland Sovereign|cFFFFFFFF",
}


class WonderlandTitleColorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wonderland-title-colors-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = {}
        for locale in subject.LOCALES:
            newline = "\r\n" if locale == "en_us" else "\n"
            for filename in ("DesigName.dat", "DesigInfo.dat"):
                rows = ["6000\tUnrelated 海神🌊", "5152\t|cffDC143C[Heir of Perseus]|cFFFFFFFF",
                        "5014\tDeep Sea Hunter"]
                for island, (identity, name, rarity, color) in reversed(list(enumerate(subject.TITLES, 1))):
                    text = name if filename == "DesigName.dat" else subject.description(island, name)
                    rows.append(f"{identity}\t{text}")
                text = newline.join(rows) + (newline if filename == "DesigInfo.dat" else "")
                path = self.root / "Localization" / locale / "Text" / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                self.before[path] = b"\xff\xfe" + text.encode("utf-16-le")
                path.write_bytes(self.before[path])

    def write_text(self, path, text):
        path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))

    def name_path(self, locale="en_us"):
        return self.root / "Localization" / locale / "Text/DesigName.dat"

    def install(self, plan=None):
        with patch.object(subject, "assert_client_closed"):
            return subject.install(self.root, plan or subject.build_plan(self.root))

    def test_exact_palette_native_spans_and_only_owned_name_rows_changed(self):
        plan = subject.build_plan(self.root)
        self.assertEqual(4, len(plan))
        self.assertEqual(2, sum(c.changed for c in plan))
        for change in plan:
            self.assertEqual(self.before[change.path], change.before)
            old = change.before[2:].decode("utf-16-le")
            new = change.after[2:].decode("utf-16-le")
            if change.path.name == "DesigInfo.dat":
                self.assertEqual(change.before, change.after)
                continue
            old_rows = old.splitlines(keepends=True)
            new_rows = new.splitlines(keepends=True)
            self.assertEqual(len(old_rows), len(new_rows))
            for before, after in zip(old_rows, new_rows):
                identity = int(before.split("\t")[0])
                if identity not in EXPECTED:
                    self.assertEqual(before, after)
                else:
                    tail = before[len(before.rstrip("\r\n")):]
                    self.assertEqual(f"{identity}\t{EXPECTED[identity]}{tail}", after)
                    self.assertEqual(before, re.sub(r"\|c[0-9a-fA-F]{8}", "", after))
        self.assertEqual(self.before, {p: p.read_bytes() for p in self.before})
        self.assertFalse((self.root / "backups").exists())

    def test_palette_identity_and_names_match_server_islands(self):
        source = Path(__file__).resolve().parent.parent / "src/Godswar.Server/Application/WorldInstances/WonderlandTitleContracts.cs"
        mappings = re.findall(r'(\d) => new\(\d, (\d+), "([^"]+)"\)', source.read_text())
        self.assertEqual([(str(i), str(t[0]), t[1]) for i, t in enumerate(subject.TITLES, 1)], mappings)
        self.assertEqual(["Uncommon", "Rare", "Rare", "Epic", "Epic", "Legendary", "Mythic", "Sovereign"],
                         [t[2] for t in subject.TITLES])

    def test_verified_four_file_backup_and_idempotence(self):
        with patch.object(subject, "assert_client_closed") as guard:
            receipt = subject.install(self.root, subject.build_plan(self.root))
        self.assertEqual(2, guard.call_count)
        self.assertEqual(2, receipt["files_changed"])
        manifest_path = Path(receipt["backup_manifest"])
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual("Verified", manifest["status"])
        self.assertEqual(subject.PATCH_ID, manifest["patch_id"])
        self.assertEqual(4, len(manifest["files"]))
        for entry in manifest["files"]:
            path = self.root / entry["path"]
            self.assertEqual(self.before[path], (manifest_path.parent / entry["path"]).read_bytes())
            self.assertEqual(digest(self.before[path]), entry["before_sha256"])
            self.assertEqual(digest(path.read_bytes()), entry["after_sha256"])
        installed = {p: p.read_bytes() for p in self.before}
        self.assertFalse(any(c.changed for c in subject.build_plan(self.root)))
        self.assertEqual("AlreadyMatches", self.install()["status"])
        self.assertEqual(installed, {p: p.read_bytes() for p in self.before})
        self.assertEqual(1, len(list((self.root / "backups/wonderland-title-colors").iterdir())))

    def test_foreign_partial_duplicate_missing_or_renamed_owned_rows_reject(self):
        path = self.name_path()
        original = Document.read(path).text
        for label, text in {
            "foreign name": original.replace("5155\tGatebreaker", "5155\tUnknown title"),
            "foreign color": original.replace("5155\tGatebreaker", "5155\t|cff000000Gatebreaker|cFFFFFFFF"),
            "partial": original.replace("5155\tGatebreaker", "5155\t" + EXPECTED[5155]),
            "duplicate": original + "\r\n5155\tGatebreaker",
            "malformed duplicate": original + "\r\n5155 other",
            "missing": original.replace("5155\tGatebreaker", "9999\tGatebreaker"),
        }.items():
            with self.subTest(label=label):
                self.write_text(path, text)
                current = path.read_bytes()
                with self.assertRaises(PatchError):
                    subject.build_plan(self.root)
                self.assertEqual(current, path.read_bytes())
        self.assertFalse((self.root / "backups").exists())

    def test_description_ownership_guard_applies_before_and_after_install(self):
        self.install()
        path = self.name_path("zh_cn").with_name("DesigInfo.dat")
        self.write_text(path, Document.read(path).text.replace("Clear Wonderland island 1", "Clear some other island"))
        current = {p: p.read_bytes() for p in self.before}
        with self.assertRaisesRegex(PatchError, "owned Wonderland pair"):
            subject.build_plan(self.root)
        self.assertEqual(current, {p: p.read_bytes() for p in self.before})

    def test_encoding_line_endings_and_size_validation(self):
        path = self.name_path()
        original = self.before[path]
        for data in (b"plain UTF8", original + b"\x00", original + b"\x00\xd8",
                     original + "\n9999\tMixed".encode("utf-16-le"),
                     original + ("x" * 10_000).encode("utf-16-le")):
            with self.subTest(data_length=len(data)):
                path.write_bytes(data)
                with self.assertRaises(PatchError):
                    subject.build_plan(self.root)

    def test_running_client_blocks_initial_and_prepublication_stages(self):
        plan = subject.build_plan(self.root)
        for effects in ([PatchError("client running")], [None, PatchError("client started")]):
            with patch.object(subject, "assert_client_closed", side_effect=effects):
                with self.assertRaises(PatchError):
                    subject.install(self.root, plan)
            self.assertEqual(self.before, {p: p.read_bytes() for p in self.before})

    def test_preflight_detects_unchanged_description_edit(self):
        plan = subject.build_plan(self.root)
        path = plan[3].path
        newer = path.read_bytes() + "\n; external edit".encode("utf-16-le")
        path.write_bytes(newer)
        with self.assertRaisesRegex(PatchError, "after preflight"):
            self.install(plan)
        self.assertEqual(newer, path.read_bytes())
        self.assertEqual(plan[0].before, plan[0].path.read_bytes())

    def test_parsed_snapshot_cannot_adopt_later_unparsed_bytes(self):
        read = subject.read_catalog
        path = self.name_path()
        newer = self.before[path] + "\r\n; concurrent".encode("utf-16-le")
        def racing_read(current):
            document = read(current)
            if current == path:
                path.write_bytes(newer)
            return document
        with patch.object(subject, "read_catalog", side_effect=racing_read):
            plan = subject.build_plan(self.root)
        self.assertEqual(self.before[path], plan[0].before)
        with self.assertRaisesRegex(PatchError, "after preflight"):
            self.install(plan)
        self.assertEqual(newer, path.read_bytes())

    def test_second_name_write_failure_rolls_back_first_exactly(self):
        plan = subject.build_plan(self.root)
        def fail_second(path, data):
            if path == plan[2].path:
                raise OSError("simulated replacement denied")
            atomic_write(path, data)
        with patch.object(subject, "atomic_write", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "replacement denied"):
                self.install(plan)
        self.assertEqual(self.before, {p: p.read_bytes() for p in self.before})
        receipts = list((self.root / "backups/wonderland-title-colors").glob("*/manifest.json"))
        self.assertEqual("RolledBack", json.loads(receipts[0].read_text())["status"])
        self.assertEqual(2, self.install()["files_changed"])

    def test_concurrent_postwrite_edit_is_preserved_during_rollback(self):
        plan = subject.build_plan(self.root)
        newer = plan[0].after + "\r\n; user edit".encode("utf-16-le")
        def race_second(path, data):
            if path == plan[2].path:
                plan[0].path.write_bytes(newer)
                raise OSError("simulated second write failure")
            atomic_write(path, data)
        with patch.object(subject, "atomic_write", side_effect=race_second):
            with self.assertRaisesRegex(PatchError, "Restore verified backups"):
                self.install(plan)
        self.assertEqual(newer, plan[0].path.read_bytes())
        receipts = list((self.root / "backups/wonderland-title-colors").glob("*/manifest.json"))
        self.assertEqual("RollbackFailed", json.loads(receipts[0].read_text())["status"])

    def test_complete_one_locale_upgrade_can_finish_other_locale(self):
        plan = subject.build_plan(self.root)
        plan[0].path.write_bytes(plan[0].after)
        updated = subject.build_plan(self.root)
        self.assertEqual([False, False, True, False], [c.changed for c in updated])
        self.assertEqual(1, self.install(updated)["files_changed"])
        self.assertFalse(any(c.changed for c in subject.build_plan(self.root)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
