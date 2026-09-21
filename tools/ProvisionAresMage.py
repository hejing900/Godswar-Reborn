"""Prepare/status by default; --apply creates only the absent local AresMage.

The live server is never stopped or started by this tool. An operator must stop
the exact reviewed image first. SQL is one guarded transaction and refuses any
existing identity. Credentials and the fresh database backup remain ACL-private.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "database/fixtures/ares-mage"
SERVER = "godswar-dev-tempest-openworld-01"
POSTGRES = "godswar-dev-postgres"
REDIS = "godswar-dev-redis-coordination"
EXPECTED_IMAGE = "sha256:0c9c7e90a488310cc87743c82d03512b62724eda93e44bdc3090fee4d1450b64"
FRAGMENTS = ("01_identity.sql", "02_equipment.sql", "03_pet.sql", "03b_talents.sql", "04_verify.sql")


def run(args, *, data=None):
    result = subprocess.run(args, input=data, capture_output=True)
    if result.returncode:
        # Never echo database SQL/parameters or dump contents through exceptions.
        raise RuntimeError(f"Command failed: {args[0]} {args[1] if len(args)>1 else ''}")
    return result.stdout


def inspect(container):
    values = json.loads(run(["docker", "inspect", container]))
    if len(values) != 1 or values[0]["Name"] != "/" + container:
        raise RuntimeError("Unexpected container identity")
    return values[0]


def psql(sql):
    return run(["docker", "exec", "-i", POSTGRES, "psql", "-X", "-q", "-A", "-t",
                "-v", "ON_ERROR_STOP=1", "-U", "godswar", "-d", "godswar"],
               data=sql.encode("utf-8")).decode("utf-8")


def status():
    server = inspect(SERVER)
    if server["Image"] != EXPECTED_IMAGE:
        raise RuntimeError("Server image differs from the reviewed release")
    postgres, redis = inspect(POSTGRES), inspect(REDIS)
    for container, role in ((server, None), (postgres, "cloned-nonproduction-authority"),
                            (redis, "disposable-coordination")):
        labels = container["Config"].get("Labels") or {}
        if labels.get("com.reborn.environment.scope") != "isolated-development" or (
                role and labels.get("com.reborn.data.role") != role):
            raise RuntimeError("Unexpected local development container scope")
    if "GODSWAR_RUNTIME_PROFILE=LocalDevelopment" not in server["Config"]["Env"]:
        raise RuntimeError("Server is not the LocalDevelopment profile")
    if not postgres["State"]["Running"] or not redis["State"]["Running"]:
        raise RuntimeError("Local PostgreSQL and Redis must be running")
    found = json.loads(psql("""BEGIN READ ONLY;
SELECT json_build_object('accounts',(SELECT count(*) FROM accounts WHERE lower(username)='aresmage'),
'characters',(SELECT count(*) FROM character_base WHERE lower(name)='aresmage'));
COMMIT;""").strip())
    return {"server_running": server["State"]["Running"], "server_image": server["Image"],
            "existing": found, "account": "aresmage", "character": "AresMage",
            "level": 140, "profession": 3, "camp": 0, "gear_count": 11,
            "quality": 10, "grade": 12, "holy_suit_code": 401,
            "talent_count": 18, "talent_rank": 60,
            "pet_species": 12, "pet_level": 120, "pet_basic": [600,100,200,150,150,300],
            "sql_files": [{"path": str(SQL_DIR / name),
                           "sha256": hashlib.sha256((SQL_DIR / name).read_bytes()).hexdigest()}
                          for name in FRAGMENTS]}


def private_directory(path):
    if os.name != "nt":
        raise RuntimeError("Apply requires the reviewed Windows workstation")
    path.mkdir(parents=True, exist_ok=False)
    identity = run(["whoami"]).decode().strip()
    run(["icacls", str(path), "/inheritance:r", "/grant:r",
         f"{identity}:(OI)(CI)F", "SYSTEM:(OI)(CI)F"])


def credential_record(password, salt):
    # Stock native login hashes the typed password before sending it.
    wire = hashlib.md5(password.encode("ascii")).hexdigest()
    key = hashlib.pbkdf2_hmac("sha256", wire.encode("ascii"), salt, 600000, 32)
    verifier = "gws$pbkdf2-sha256$v1$600000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(key).decode()
    return wire, verifier


def render_sql(verifier):
    if not verifier.startswith("gws$pbkdf2-sha256$v1$600000$") or "'" in verifier:
        raise ValueError("Unexpected credential verifier format")
    sql = "\n".join((SQL_DIR / name).read_text(encoding="utf-8") for name in FRAGMENTS)
    if sql.count("__PRIVATE_VERIFIER__") != 1:
        raise ValueError("SQL must contain one private credential placeholder")
    return sql.replace("__PRIVATE_VERIFIER__", "'" + verifier + "'")


def validate_plan_sql(plan):
    for entry in plan["sql_files"]:
        if hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("SQL changed after the reviewed plan was captured")


def apply(plan, directory):
    if plan["server_running"]:
        raise RuntimeError("Stop the reviewed Tempest server before applying")
    if plan["existing"] != {"accounts": 0, "characters": 0}:
        raise RuntimeError("AresMage already exists; refusing overwrite")
    # IDs do not exist yet, so only the canonical username claim can exist.
    # Send Redis auth through stdin to a fixed shell command, never argv/logs.
    redis_secret = (ROOT / "artifacts/development-stack/redis.password").read_text().strip()
    if len(redis_secret) != 64 or any(c not in "0123456789abcdef" for c in redis_secret):
        raise RuntimeError("Local Redis credential is malformed")
    opaque = hashlib.sha256(b"username\0aresmage").hexdigest().upper()[:32]
    key = "godswar:tempest-dev:v1:login-name:" + opaque
    shell = 'IFS= read -r REDISCLI_AUTH; export REDISCLI_AUTH; exec redis-cli --user godswar_runtime --no-auth-warning -n 0 EXISTS "$1"'
    exists = run(["docker", "exec", "-i", REDIS, "sh", "-c", shell, "mage-lease-check", key],
                 data=(redis_secret + "\n").encode()).decode().strip()
    if exists != "0":
        raise RuntimeError("AresMage login-name lease remains or could not be verified")
    private_directory(directory)
    backup = directory / "godswar-before-aresmage.dump"
    with backup.open("xb") as stream:
        result = subprocess.run(["docker", "exec", POSTGRES, "pg_dump", "-U", "godswar",
                                 "-d", "godswar", "-Fc"], stdout=stream, stderr=subprocess.PIPE)
    if result.returncode or backup.stat().st_size == 0:
        raise RuntimeError("Fresh database backup failed")
    # pg_restore validates the actual saved bytes via stdin without temp paths.
    with backup.open("rb") as stream:
        result = subprocess.run(["docker", "exec", "-i", POSTGRES, "pg_restore", "--list"],
                                stdin=stream, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError("Fresh database backup failed validation")
    if inspect(SERVER)["State"]["Running"] or inspect(SERVER)["Image"] != EXPECTED_IMAGE:
        raise RuntimeError("Server changed while making backup")
    password = secrets.token_urlsafe(18)  #24 printable ASCII, within native32.
    wire, verifier = credential_record(password, secrets.token_bytes(16))
    credential_file = directory / "credentials.private.json"
    credential_file.write_text(json.dumps({"username": "aresmage", "password": password,
        "wire_password_md5": wire, "credential_format": "native-md5/pbkdf2-sha256-v1"}, indent=2), encoding="utf-8")
    validate_plan_sql(plan)
    sql = render_sql(verifier)
    validate_plan_sql(plan)
    output = psql(sql)
    receipts = [line.removeprefix("ARES_MAGE_RECEIPT|") for line in output.splitlines()
                if line.startswith("ARES_MAGE_RECEIPT|")]
    if len(receipts) != 1:
        raise RuntimeError("No unique committed creation receipt; inspect private backup before retry")
    receipt = json.loads(receipts[0])
    receipt.update({"credential_file": str(credential_file), "backup": str(backup),
                    "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                    "server_image": EXPECTED_IMAGE, "sql_files": plan["sql_files"]})
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create the reviewed absent identity; requires stopped server")
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    plan = status()
    if args.apply:
        directory = args.artifact_dir or ROOT / "artifacts" / ("ares-mage-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        result = apply(plan, directory.resolve())
    else:
        result = plan
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
