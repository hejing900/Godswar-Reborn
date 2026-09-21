"""Hermetic safety/protocol checks; never contacts Docker or a database."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("mage", Path(__file__).with_name("ProvisionAresMage.py"))
mage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mage)


class ProvisionTests(unittest.TestCase):
    def test_native_wire_credential_is_hashed_not_typed_password(self):
        password, salt = "FixtureOnly_AsciiPass", bytes(range(16))
        wire, verifier = mage.credential_record(password, salt)
        self.assertEqual(wire, hashlib.md5(password.encode("ascii")).hexdigest())
        parts = verifier.split("$")
        self.assertEqual(parts[:4], ["gws", "pbkdf2-sha256", "v1", "600000"])
        self.assertEqual(base64.b64decode(parts[4]), salt)
        key = base64.b64decode(parts[5])
        self.assertEqual(key, hashlib.pbkdf2_hmac("sha256", wire.encode(), salt, 600000, 32))
        self.assertNotEqual(key, hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000, 32))

    def test_live_or_existing_identity_never_reaches_io(self):
        with patch.object(mage, "run", side_effect=AssertionError("unexpected IO")):
            with self.assertRaisesRegex(RuntimeError, "Stop"):
                mage.apply({"server_running": True}, Path("unused"))
            with self.assertRaisesRegex(RuntimeError, "exists"):
                mage.apply({"server_running": False, "existing": {"accounts": 1, "characters": 1}}, Path("unused"))

    def test_changed_sql_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.sql"
            path.write_bytes(b"SELECT 1;")
            plan = {"sql_files": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
            mage.validate_plan_sql(plan)
            path.write_bytes(b"SELECT 2;")
            with self.assertRaisesRegex(RuntimeError, "SQL changed"):
                mage.validate_plan_sql(plan)

    def test_credential_is_quoted_once_inside_one_transaction(self):
        _, verifier = mage.credential_record("FixtureOnly_AsciiPass", bytes(range(16)))
        sql = mage.render_sql(verifier)
        self.assertEqual(sql.count(verifier), 1)
        self.assertNotIn("__PRIVATE_VERIFIER__", sql)
        self.assertEqual(sql.count("BEGIN ISOLATION LEVEL SERIALIZABLE;"), 1)
        self.assertEqual(sql.count("COMMIT;"), 1)
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        with self.assertRaises(ValueError):
            mage.render_sql(verifier + "'")

    def test_initial_talents_are_before_vitals_and_preserve_existing_rows(self):
        _, verifier = mage.credential_record("FixtureOnly_AsciiPass", bytes(range(16)))
        sql = mage.render_sql(verifier)
        insertion = sql.index("INSERT INTO character_talents(")
        self.assertLess(sql.index("INSERT INTO character_base("), insertion)
        self.assertLess(insertion, sql.index("CREATE TEMP TABLE mage_vitals"))
        self.assertIn("SELECT c.character_id,t.talent_id,60,0,now()", sql)
        self.assertIn("Initial mage talents already exist; no overwrite allowed", sql)
        self.assertIn("d.required_prefix_rank=0 AND d.required_total_rank=0", sql)
        self.assertIn("WHEN 'character_talents' THEN format('user_id<>%s',m.character_id)", sql)
        self.assertIn('AND "SkillPoint"=10 AND "SkillExp"=0', sql)


if __name__ == "__main__":
    unittest.main()
