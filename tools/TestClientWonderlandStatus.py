#!/usr/bin/env python3
"""Hermetic regression checks for the Wonderland status asset transaction."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import PatchClientWonderlandStatus as subject
from holy_suit_tiers.text import Document, PatchError
from holy_suit_tiers.transaction import atomic_write


FIXTURE = "; Existing status data must remain byte-identical.\r\n" + "\r\n".join(
    f"[{identity}]\r\nName=Original\r\nKind={identity}\r\nIconPos={icon}\r\n"
    for identity, icon in ((237, "216,0"), (454, "324,72"), (100, "144,36"))) + (
    "\r\n[330]\r\nName=Stuned\r\nKind=11\r\nEffect=0,2,3,4,5,6\r\n"
    "Values=1,1,1,1,1,1\r\nInterval=0,0,0,0,0,0\r\nIconPos=252,108\r\n"
    "\r\n[360]\r\nName=Magic Locked\r\nKind=12\r\nEffect=3,4\r\n"
    "Values=1,1\r\nInterval=0,0\r\nIconPos=540,72\r\n")


class WonderlandStatusPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wonderland-status-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = b"\xff\xfe" + FIXTURE.encode("utf-16-le")
        for locale in subject.LOCALES:
            path = self.root / "Localization" / locale / "Settings/Sys/Status.ini"
            path.parent.mkdir(parents=True)
            path.write_bytes(self.original)

    def test_exact_control_effects_and_server_only_stat_modifiers(self):
        plan = subject.build_plan(self.root)
        self.assertEqual(len(plan), 2)
        for change in plan:
            self.assertTrue(change.after.startswith(self.original))
            text = change.after[2:].decode("utf-16-le")
            for identity, seconds, style in ((1510, 15, 1), (1511, 15, 1), (1512, 2, 0),
                                              (1513, 2, 0), (1514, 8, 0), (1515, 10, 0)):
                block = text.split(f"[{identity}]", 1)[1].split("\r\n[", 1)[0]
                self.assertIn(f"Time={seconds}\r\n", block)
                self.assertIn(f"Style={style}\r\n", block)
                control = {1512: "Effect=0,2,3,4,5,6\r\nValues=1,1,1,1,1,1\r\nInterval=0,0,0,0,0,0\r\n",
                           1513: "Effect=3,4\r\nValues=1,1\r\nInterval=0,0\r\n"}
                self.assertIn(control.get(identity, "Effect=-1\r\nValues=0\r\nInterval=0\r\n"), block)
                if identity in (1512, 1513):
                    self.assertIn("IconPos=" + ("252,108" if identity == 1512 else "540,72"), block)
                self.assertIn("EffectDisplay=-1\r\nRideId=-1\r\nAction=1", block)
            self.assertIn("25000", text)
            self.assertIn("40%", text)
            self.assertIn("50%", text)

    def install_v1_fixture(self):
        before = {}
        for locale in subject.LOCALES:
            path = self.root / "Localization" / locale / "Settings/Sys/Status.ini"
            legacy = "\r\n\r\n".join(subject.section(row, locale, "\r\n")
                                       for row in subject.definitions(subject.LEGACY_DEFINITIONS))
            text = FIXTURE + "\r\n" + legacy + "\r\n\r\n[8000]\r\nName=Unrelated\r\nKind=20\r\n"
            before[path] = b"\xff\xfe" + text.encode("utf-16-le")
            path.write_bytes(before[path])
        return before

    def test_exact_v1_upgrade_preserves_other_statuses_and_backup(self):
        before = self.install_v1_fixture()
        plan = subject.build_plan(self.root)
        for change in plan:
            old = change.before[2:].decode("utf-16-le")
            new = change.after[2:].decode("utf-16-le")
            self.assertTrue(new.startswith(FIXTURE))
            self.assertTrue(new.endswith("[8000]\r\nName=Unrelated\r\nKind=20\r\n"))
            for identity in (1510, 1511, 1514, 1515):
                block = lambda text: text.split(f"[{identity}]", 1)[1].split("\r\n[", 1)[0]
                self.assertEqual(block(old), block(new))
            self.assertNotEqual(old, new)
        with patch.object(subject, "assert_client_closed"):
            result = subject.install(self.root, plan)
        receipt = Path(result["backup_manifest"])
        self.assertEqual(json.loads(receipt.read_text())["patch_id"], "reborn.wonderland-status.v2")
        for path, original in before.items():
            self.assertEqual((receipt.parent / path.relative_to(self.root)).read_bytes(), original)
        self.assertFalse(any(change.changed for change in subject.build_plan(self.root)))

    def test_modified_or_mixed_v1_v2_owned_sets_are_not_overwritten(self):
        for mutation in ("modified", "mixed"):
            with self.subTest(mutation=mutation):
                before = self.install_v1_fixture()
                path = next(iter(before))
                text = before[path][2:].decode("utf-16-le")
                old = subject.section(subject.definitions(subject.LEGACY_DEFINITIONS)[2], "en_us", "\r\n")
                new = subject.section(subject.definitions()[2], "en_us", "\r\n") if mutation == "mixed" else old.replace("Effect=-1", "Effect=99")
                path.write_bytes(b"\xff\xfe" + text.replace(old, new).encode("utf-16-le"))
                occupied = path.read_bytes()
                with self.assertRaisesRegex(PatchError, "occupied, partial, or modified"):
                    subject.build_plan(self.root)
                self.assertEqual(path.read_bytes(), occupied)

    def test_native_control_reference_change_and_existing_kind_collision_rejected(self):
        for field in ("Effect=3,4", "Values=1,1", "Interval=0,0", "IconPos=540,72"):
            with self.subTest(field=field), self.assertRaisesRegex(PatchError, "Native control status"):
                document = Document(FIXTURE.replace(field + "\r\n", field + ",99\r\n"), "utf-16-le", b"\xff\xfe", "\r\n")
                subject.patch_text(document, "en_us")
        document = Document(FIXTURE, "utf-16-le", b"\xff\xfe", "\r\n")
        installed = subject.patch_text(document, "en_us")
        with self.assertRaisesRegex(PatchError, "kind 1013"):
            subject.patch_text(Document(installed + "\r\n[8001]\r\nKind=1013\r\n", "utf-16-le", b"\xff\xfe", "\r\n"), "en_us")

    def test_server_status_id_parity(self):
        source = Path(__file__).resolve().parent.parent / "src/Godswar.Server/State/WonderlandClientStatusIds.cs"
        actual = dict(re.findall(r"public const uint (\w+) = (\d+);", source.read_text()))
        self.assertEqual(actual, {"PetbirdBlessing": "1510", "PutridBirdBlessing": "1511",
                                  "Stunned": "1512", "Silenced": "1513", "SpearBlast": "1514", "ArmorRend": "1515"})
        self.assertEqual(sorted(int(i) for i in actual.values()), [r["id"] for r in subject.definitions()])

    def test_install_backup_readback_and_idempotence(self):
        with patch.object(subject, "assert_client_closed") as guard:
            result = subject.install(self.root, subject.build_plan(self.root))
            self.assertEqual(guard.call_count, 2)
        self.assertEqual(result["files_changed"], 2)
        receipt = Path(result["backup_manifest"])
        self.assertEqual(json.loads(receipt.read_text())["status"], "Verified")
        for locale in subject.LOCALES:
            backup = receipt.parent / "Localization" / locale / "Settings/Sys/Status.ini"
            self.assertEqual(backup.read_bytes(), self.original)
        self.assertFalse(any(c.changed for c in subject.build_plan(self.root)))
        self.assertEqual(subject.install(self.root, subject.build_plan(self.root))["files_changed"], 0)

    def test_foreign_status_and_partial_install_fail_before_mutation(self):
        path = subject.build_plan(self.root)[0].path
        path.write_bytes(self.original + "\r\n[1510]\r\nName=Other\r\n".encode("utf-16-le"))
        before = path.read_bytes()
        with self.assertRaisesRegex(PatchError, "occupied, partial, or modified"):
            subject.build_plan(self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_duplicate_sections_and_kind_collision_fail(self):
        for extra in ("\r\n[237]\r\nName=Duplicate\r\n", "\r\n[20]\r\nKind=1011\r\n"):
            document = Document(FIXTURE + extra, "utf-16-le", b"\xff\xfe", "\r\n")
            with self.assertRaises(PatchError):
                subject.patch_text(document, "en_us")

    def test_invalid_encoding_rejected(self):
        path = subject.build_plan(self.root)[0].path
        path.write_text(FIXTURE, encoding="utf-8")
        with self.assertRaisesRegex(PatchError, "UTF-16LE"):
            subject.build_plan(self.root)

    def test_running_client_prevents_write(self):
        plan = subject.build_plan(self.root)
        with patch.object(subject, "assert_client_closed", side_effect=PatchError("client is running")):
            with self.assertRaises(PatchError):
                subject.install(self.root, plan)
        self.assertTrue(all(c.path.read_bytes() == c.before for c in plan))

    def test_second_file_failure_rolls_back_first_exactly(self):
        plan = subject.build_plan(self.root)
        failed = False
        def fail_once(path, data):
            nonlocal failed
            if path == plan[1].path and data == plan[1].after and not failed:
                failed = True
                raise OSError("injected second file write failure")
            atomic_write(path, data)
        with patch.object(subject, "assert_client_closed"), patch.object(subject, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "second file"):
                subject.install(self.root, plan)
        self.assertTrue(all(c.path.read_bytes() == c.before for c in plan))
        receipts = list((self.root / "backups/wonderland-status").glob("*/manifest.json"))
        self.assertEqual(json.loads(receipts[0].read_text())["status"], "RolledBack")

    def test_preflight_race_preserves_newer_file(self):
        plan = subject.build_plan(self.root)
        newer = self.original + "\r\n; concurrent change\r\n".encode("utf-16-le")
        plan[1].path.write_bytes(newer)
        with patch.object(subject, "assert_client_closed"):
            with self.assertRaisesRegex(PatchError, "after preflight"):
                subject.install(self.root, plan)
        self.assertEqual(plan[0].path.read_bytes(), self.original)
        self.assertEqual(plan[1].path.read_bytes(), newer)

    def test_upgrade_rollback_never_overwrites_unknown_concurrent_edit(self):
        self.install_v1_fixture()
        plan = subject.build_plan(self.root)
        newer = plan[0].after + "\r\n; another editor changed this file\r\n".encode("utf-16-le")
        def fail_after_concurrent_edit(path, data):
            if path == plan[1].path and data == plan[1].after:
                plan[0].path.write_bytes(newer)
                raise OSError("second file failed after concurrent edit")
            atomic_write(path, data)
        with patch.object(subject, "assert_client_closed"), patch.object(subject, "atomic_write", side_effect=fail_after_concurrent_edit):
            with self.assertRaisesRegex(PatchError, "Restore verified backups"):
                subject.install(self.root, plan)
        self.assertEqual(plan[0].path.read_bytes(), newer)
        self.assertEqual(plan[1].path.read_bytes(), plan[1].before)
        receipt = next((self.root / "backups/wonderland-status").glob("*/manifest.json"))
        self.assertEqual(json.loads(receipt.read_text())["status"], "RollbackFailed")
        self.assertTrue(all((receipt.parent / change.path.relative_to(self.root)).read_bytes() == change.before for change in plan))

    def test_preflight_uses_parsed_bytes_not_a_later_concurrent_read(self):
        original_read = subject.Document.read
        changed = []
        def read_then_edit(path):
            document = original_read(path)
            if not changed:
                changed.append(path)
                path.write_bytes(self.original + "\r\n; edited during preflight\r\n".encode("utf-16-le"))
            return document
        with patch.object(subject.Document, "read", side_effect=read_then_edit):
            plan = subject.build_plan(self.root)
        newer = changed[0].read_bytes()
        self.assertEqual(plan[0].before, self.original)
        with patch.object(subject, "assert_client_closed"), self.assertRaisesRegex(PatchError, "after preflight"):
            subject.install(self.root, plan)
        self.assertEqual(changed[0].read_bytes(), newer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
