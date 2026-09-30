from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "review/secret_custody_c2_candidate.sql"
ROLLBACK = ROOT / "review/secret_custody_c2_rollback.sql"


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def executable_sql(text: str) -> str:
    return "\n".join(
        line for line in text.lower().splitlines()
        if not line.lstrip().startswith("--")
    )


def main() -> None:
    require(CANDIDATE.is_file(), "c2_candidate_missing")
    require(ROLLBACK.is_file(), "c2_rollback_missing")
    require("supabase/migrations" not in str(CANDIDATE), "c2_candidate_in_migrations")
    require("supabase/migrations" not in str(ROLLBACK), "c2_rollback_in_migrations")

    candidate_raw = CANDIDATE.read_text(encoding="utf-8")
    rollback_raw = ROLLBACK.read_text(encoding="utf-8")
    candidate = executable_sql(candidate_raw)
    rollback = executable_sql(rollback_raw)

    for marker in (
        "data api disabled",
        "service/secret key not distributed to runtime",
        "postgres ssl enforcement enabled",
        "ingress restricted to the approved host cidr",
    ):
        require(marker in candidate_raw.lower(), f"c2_management_gate_comment_missing:{marker}")

    for marker in (
        "create role agent_secret_broker",
        "create role agent_secret_host",
        "password null",
        "create schema agent_credential_private authorization postgres",
        "alter table agent_credential_private.bindings force row level security",
        "alter table agent_credential_private.host_bindings force row level security",
        "security definer",
        "grant execute on function agent_credential_private.read_binding(text)",
        "grant execute on function agent_credential_private.cas_binding(text,bigint,jsonb)",
        "grant select on vault.decrypted_secrets to agent_secret_broker",
        "grant delete on vault.secrets to agent_secret_broker",
        "grant execute on function vault.update_secret(uuid,text,text,text,uuid)",
    ):
        require(marker in candidate, f"c2_candidate_marker_missing:{marker}")

    require("phase_b_preflight_service_role_vault_isolation_blocker" not in candidate,
            "shared_staging_service_role_blocker_carried_into_c2")
    require("perform vault.create_secret" not in candidate, "c2_candidate_creates_vault_secret")
    require("insert into vault.secrets" not in candidate, "c2_candidate_inserts_vault_secret")
    require("grant execute on function vault.create_secret" not in candidate,
            "c2_candidate_grants_create_secret")
    require("revoke usage on schema vault from service_role" not in candidate,
            "c2_candidate_revokes_platform_vault_schema")
    require("revoke select on vault.decrypted_secrets from service_role" not in candidate,
            "c2_candidate_revokes_platform_decrypted_access")
    require("revoke delete on vault.secrets from service_role" not in candidate,
            "c2_candidate_revokes_platform_vault_delete")
    require("cascade" not in candidate, "c2_candidate_contains_cascade")

    for marker in (
        "revoke execute on function agent_credential_private.read_binding(text)",
        "revoke execute on function agent_credential_private.cas_binding(text,bigint,jsonb)",
        "pg_catalog.pg_stat_activity",
        "c2_rollback_nonempty_private_state",
        "drop role agent_secret_host",
        "drop role agent_secret_broker",
    ):
        require(marker in rollback, f"c2_rollback_marker_missing:{marker}")

    require("cascade" not in rollback, "c2_rollback_contains_cascade")
    require("delete from vault.secrets" not in rollback, "c2_rollback_deletes_vault_secret")

    print("secret_custody_c2_review_artifacts: ok")


if __name__ == "__main__":
    main()
