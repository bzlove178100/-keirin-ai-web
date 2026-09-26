"""Run the synthetic SQL/ACL prototype in the disposable PostgreSQL CI service."""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    if (os.environ.get("AGENT_EPHEMERAL_DB_TEST") != "1"
            or os.environ.get("PGHOST") != "127.0.0.1"
            or os.environ.get("PGDATABASE") != "agent_checkpoint_ci"):
        raise SystemExit("refusing_non_ephemeral_database")
    parts = [
        "BEGIN;",
        "SET LOCAL statement_timeout = '15s';",
        "SET LOCAL lock_timeout = '3s';",
        (ROOT / "tests/support/vault_postgres_contract.sql").read_text(),
        (ROOT / "tests/vault_postgres_contract_cases.sql").read_text(),
        "ROLLBACK;",
    ]
    result = subprocess.run(
        ["psql", "-X", "--set", "ON_ERROR_STOP=1", "--quiet"],
        input="\n".join(parts), text=True, capture_output=True, timeout=90,
    )
    if result.returncode:
        # This input is entirely synthetic; no deployed credential is ever accepted.
        print(result.stderr)
        raise SystemExit("synthetic_vault_contract_failed")
    print("Synthetic PostgreSQL secret boundary: ACL, CAS, rollback, revocation PASS")


if __name__ == "__main__":
    main()
