"""Run the synthetic SQL/ACL contract in the disposable PostgreSQL 17 CI service."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PSQL = [
    "psql", "-X", "--set", "ON_ERROR_STOP=1", "--quiet", "--tuples-only", "--no-align"
]
TEST_ROLES = (
    "secret_test_host_a",
    "secret_test_host_b",
    "secret_test_broker",
    "anon",
    "authenticated",
    "service_role",
    "authenticator",
)


def _assert_ephemeral_database() -> None:
    if (
        os.environ.get("AGENT_EPHEMERAL_DB_TEST") != "1"
        or os.environ.get("PGHOST") != "127.0.0.1"
        or os.environ.get("PGDATABASE") != "agent_checkpoint_ci"
    ):
        raise SystemExit("refusing_non_ephemeral_database")


def _run_sql(sql: str, *, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        PSQL,
        input=sql,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _cleanup() -> None:
    role_array = ",".join("'" + value.replace("'", "''") + "'" for value in TEST_ROLES)
    sql = f"""
DROP SCHEMA IF EXISTS agent_credential_private CASCADE;
DROP SCHEMA IF EXISTS synthetic_vault CASCADE;
DROP SCHEMA IF EXISTS auth CASCADE;
DO $cleanup$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY[{role_array}] LOOP
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
      EXECUTE format('DROP OWNED BY %I', role_name);
      EXECUTE format('DROP ROLE %I', role_name);
    END IF;
  END LOOP;
END
$cleanup$;
"""
    result = _run_sql(sql, timeout=30)
    if result.returncode:
        raise RuntimeError("synthetic_vault_cleanup_failed")


def _replacement(attempt_id: str) -> str:
    return json.dumps(
        {
            "schema_version": "credential-refresh-secret-record-v1",
            "provider_id": "provider-a",
            "account_id": "account-a",
            "capabilities": ["read:one", "write:one"],
            "version": 1,
            "state": "refreshing",
            "refresh_secret": "SYNTHETIC:a0",
            "refresh_generation": 0,
            "active_attempt_id": attempt_id,
            "last_attempt_id": None,
            "failure": None,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _race_sql(attempt_id: str) -> str:
    replacement = _replacement(attempt_id)
    return f"""
BEGIN;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '5s';
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT pg_catalog.pg_sleep(0.2);
SELECT agent_credential_private.cas_binding(
  'binding-a', 0, $json${replacement}$json$::jsonb
)->>'state' = 'refreshing';
COMMIT;
"""


def _run_independent_session_race() -> None:
    fault = _run_sql(
        "INSERT INTO synthetic_vault.test_faults VALUES ('hold_initial_cas_lock');"
    )
    if fault.returncode:
        raise RuntimeError("synthetic_vault_race_setup_failed")

    processes = [
        subprocess.Popen(
            PSQL + ["--set", "VERBOSITY=verbose", "-c", _race_sql("race-attempt-a")],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ),
        subprocess.Popen(
            PSQL + ["--set", "VERBOSITY=verbose", "-c", _race_sql("race-attempt-b")],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ),
    ]
    outcomes: list[tuple[int, str, str]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        outcomes.append((process.returncode, stdout, stderr))

    successes = [value for value in outcomes if value[0] == 0]
    conflicts = [value for value in outcomes if value[0] != 0]
    if len(successes) != 1 or len(conflicts) != 1:
        raise RuntimeError("synthetic_vault_race_outcome_invalid")
    if "P0002" not in conflicts[0][2] or "credential_version_conflict" not in conflicts[0][2]:
        raise RuntimeError("synthetic_vault_race_conflict_not_fixed")

    verify = _run_sql(
        """
SET SESSION AUTHORIZATION secret_test_host_a;
SELECT (
  record->>'version' = '1'
  AND record->>'state' = 'refreshing'
  AND record->>'refresh_generation' = '0'
  AND record->>'refresh_secret' = 'SYNTHETIC:a0'
  AND record->>'active_attempt_id' IN ('race-attempt-a','race-attempt-b')
  AND record->'last_attempt_id' = 'null'::jsonb
  AND record->'failure' = 'null'::jsonb
)
FROM (
  SELECT agent_credential_private.read_binding('binding-a') AS record
) AS observed;
""",
        timeout=30,
    )
    if verify.returncode or verify.stdout.strip() != "t":
        raise RuntimeError("synthetic_vault_race_readback_invalid")


def main() -> None:
    _assert_ephemeral_database()
    _cleanup()
    try:
        parts = [
            "BEGIN;",
            "SET LOCAL statement_timeout = '15s';",
            "SET LOCAL lock_timeout = '3s';",
            (ROOT / "tests/support/vault_postgres_contract.sql").read_text(),
            "COMMIT;",
            "BEGIN;",
            "SET LOCAL statement_timeout = '15s';",
            "SET LOCAL lock_timeout = '3s';",
            (ROOT / "tests/vault_postgres_contract_cases.sql").read_text(),
            "ROLLBACK;",
        ]
        result = _run_sql("\n".join(parts))
        if result.returncode:
            # Inputs are synthetic; never print SQL or any future secret-bearing stdout.
            print(result.stderr)
            raise SystemExit("synthetic_vault_contract_failed")

        _run_independent_session_race()
    finally:
        _cleanup()

    print(
        "Synthetic PostgreSQL secret boundary: full record, ACL, rollback, "
        "revocation, independent-session CAS PASS"
    )


if __name__ == "__main__":
    main()
