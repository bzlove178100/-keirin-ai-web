from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "SECRET_CUSTODY_C0_C1_EVIDENCE.md"
C2_REVIEW = ROOT / "SECRET_CUSTODY_C2_REVIEW.md"
PREFLIGHT = ROOT / "review/secret_custody_c2_db_preflight.sql"


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    require(EVIDENCE.is_file(), "secret_custody_c0_c1_evidence_missing")
    require(C2_REVIEW.is_file(), "secret_custody_c2_review_missing")
    require(PREFLIGHT.is_file(), "secret_custody_c2_preflight_missing")

    evidence = EVIDENCE.read_text(encoding="utf-8").lower()
    review = C2_REVIEW.read_text(encoding="utf-8").lower()
    preflight = PREFLIGHT.read_text(encoding="utf-8").lower()

    for marker in (
        "0 per month",
        "not approved for real always-on credential custody",
        "data api disabled state",
        "ssl-enforcement state",
        "network-restriction state",
        "no ddl/dml statement was submitted",
    ):
        require(marker in evidence, f"c0_c1_evidence_marker_missing:{marker}")

    for marker in (
        "review only — live schema apply blocked",
        "data api disabled",
        "no custody-project service/secret key distributed",
        "ssl enforcement enabled",
        "ingress restricted to the approved host cidr",
        "does not authorize",
        "creating a real or synthetic vault secret",
    ):
        require(marker in review, f"c2_review_marker_missing:{marker}")

    require("vault.secrets" in preflight, "preflight_safety_comment_missing")
    require("vault.decrypted_secrets" in preflight, "preflight_safety_comment_missing_decrypted")

    executable = "\n".join(
        line for line in preflight.splitlines() if not line.lstrip().startswith("--")
    )
    require("from vault.secrets" not in executable, "preflight_reads_vault_secrets")
    require("from vault.decrypted_secrets" not in executable, "preflight_reads_decrypted_secrets")
    require("insert into" not in executable, "preflight_contains_insert")
    require("update vault." not in executable, "preflight_contains_vault_update")
    require("delete from" not in executable, "preflight_contains_delete")
    require("create role" not in executable, "preflight_contains_create_role")
    require("create schema" not in executable, "preflight_contains_create_schema")
    require("grant " not in executable, "preflight_contains_grant")
    require("revoke " not in executable, "preflight_contains_revoke")

    print("secret_custody_c0_c1_review: ok")


if __name__ == "__main__":
    main()
