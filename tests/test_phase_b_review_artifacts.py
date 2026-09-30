from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "review" / "staging_secret_backend_phase_b_candidate.sql"
ROLLBACK = ROOT / "review" / "staging_secret_backend_phase_b_rollback.sql"
REVIEW = ROOT / "STAGING_SECRET_BACKEND_PHASE_B_DDL_REVIEW.md"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def sql_without_line_comments(text: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    require(FORWARD.is_file(), "phase_b_forward_missing")
    require(ROLLBACK.is_file(), "phase_b_rollback_missing")
    require(REVIEW.is_file(), "phase_b_review_missing")
    require("supabase/migrations" not in FORWARD.as_posix(), "forward_in_migration_path")
    require("supabase/migrations" not in ROLLBACK.as_posix(), "rollback_in_migration_path")

    forward_raw = FORWARD.read_text(encoding="utf-8")
    rollback_raw = ROLLBACK.read_text(encoding="utf-8")
    review_raw = REVIEW.read_text(encoding="utf-8")
    forward = normalized(sql_without_line_comments(forward_raw))
    rollback = normalized(sql_without_line_comments(rollback_raw))
    review = normalized(review_raw)

    blocker = "phase_b_preflight_service_role_vault_isolation_blocker"
    first_mutation = forward.find("create role agent_secret_broker")
    require(blocker in forward, "service_role_blocker_missing")
    require(first_mutation >= 0, "first_expected_ddl_missing")
    require(forward.find(blocker) < first_mutation, "blocker_not_before_first_ddl")

    require("password null" in forward, "host_password_not_null")
    require(
        "grant execute on function vault.create_secret" not in forward,
        "runtime_broker_can_create_vault_secret",
    )
    require("insert into vault." not in forward, "forward_contains_vault_provisioning")

    # The review must not silently mutate the shared platform role's Vault grants.
    forbidden_service_role_vault_revokes = (
        "revoke usage on schema vault from service_role",
        "revoke select on vault.secrets from service_role",
        "revoke select on vault.decrypted_secrets from service_role",
        "revoke delete on vault.secrets from service_role",
        "revoke execute on function vault.create_secret",
        "revoke execute on function vault.update_secret",
    )
    for fragment in forbidden_service_role_vault_revokes:
        if fragment.startswith("revoke execute"):
            require(
                not re.search(
                    re.escape(fragment) + r".*?from service_role",
                    forward,
                ),
                f"forbidden_platform_vault_revoke:{fragment}",
            )
        else:
            require(fragment not in forward, f"forbidden_platform_vault_revoke:{fragment}")

    require(not re.search(r"\bcascade\b", rollback), "rollback_uses_cascade")
    require("phase_b_rollback_active_host_session" in rollback, "active_session_guard_missing")
    require("phase_b_rollback_nonempty_private_state" in rollback, "nonempty_state_guard_missing")

    require("review only" in review, "review_only_status_missing")
    require("blocked from apply" in review, "apply_blocker_status_missing")
    require("does not authorize" in review, "non_authorization_section_missing")

    print("phase_b_review_artifacts: ok")


if __name__ == "__main__":
    main()
