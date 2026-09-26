"""Execute real PostgreSQL contract tests only against the disposable CI service."""
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def design_body(path):
    text = path.read_text(encoding="utf-8")
    # Only remove the outer rollback-only wrapper inside this synthetic test.
    if re.search(r"\bcommit\s*;", text, re.I):
        raise ValueError("design_must_not_commit")
    text, begins = re.subn(r"^begin;\s*$", "", text, flags=re.M | re.I)
    text, ends = re.subn(r"^rollback;\s*$", "", text, flags=re.M | re.I)
    if begins != 1 or ends != 1:
        raise ValueError("one_rollback_wrapper_required")
    return text


def main():
    if (os.environ.get("AGENT_EPHEMERAL_DB_TEST") != "1"
            or os.environ.get("PGHOST") != "127.0.0.1"
            or os.environ.get("PGDATABASE") != "agent_checkpoint_ci"):
        raise SystemExit("refusing_non_ephemeral_database")
    parts = ["begin;", (ROOT / "tests/agent_checkpoint_bootstrap.sql").read_text()]
    for name in ("agent_runtime_state_v1.sql", "agent_runtime_checkpoints_v2.sql"):
        parts.append(design_body(ROOT / "supabase/schema" / name))
    for name in (
        "20260925122122_agent_runtime_queue_lease.sql",
        "20260926123000_agent_runtime_exact_task_claim.sql",
        "20260926132000_agent_trusted_run_single_active_guard.sql",
    ):
        parts.append((ROOT / "supabase/migrations" / name).read_text(encoding="utf-8"))
    parts += [
        (ROOT / "tests/agent_checkpoint_cases.sql").read_text(),
        (ROOT / "tests/agent_queue_lease_cases.sql").read_text(),
        (ROOT / "tests/agent_exact_task_claim_cases.sql").read_text(),
        (ROOT / "tests/agent_trusted_run_single_active_cases.sql").read_text(),
        "rollback;",
    ]
    subprocess.run(["psql", "-X", "--set", "ON_ERROR_STOP=1", "--quiet"],
                   input="\n".join(parts), text=True, check=True)
    print("PostgreSQL checkpoint/RLS/CAS plus queue fencing, exact-task claim, and single-active guard: PASS")


if __name__ == "__main__":
    main()
