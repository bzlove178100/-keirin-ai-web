import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_HOST_RECOVERY_ROLLBACK_REVIEW.md"
PLAN = ROOT / "review/secret_custody_host_recovery.plan.json"
VALIDATOR = ROOT / "review/validate_secret_custody_host_recovery_plan.py"


def main():
    doc = DOC.read_text(encoding="utf-8")
    raw = PLAN.read_text(encoding="utf-8")
    data = json.loads(raw)
    validator = VALIDATOR.read_text(encoding="utf-8")

    required_doc = [
        "review only — no live recovery",
        "fail closed",
        "runtime remains disabled",
        "host remains no-secret",
        "AWS resource destruction is deliberately outside this plan",
        "does not authorize or perform AWS provisioning",
    ]
    for marker in required_doc:
        assert marker in doc, f"missing recovery review marker: {marker}"

    assert data["status"] == "review_only"
    assert data["authorized_for_live_recovery"] is False
    assert data["scope"]["host_must_remain_no_secret"] is True
    assert data["scope"]["runtime_must_remain_disabled"] is True
    assert all(v is False for v in data["protected_domains"].values())
    assert data["aws_recovery"]["separate_live_authorization_required"] is True
    assert data["aws_recovery"]["automatic_instance_delete_allowed"] is False
    assert data["network_recovery"]["automatic_firewall_relaxation_allowed"] is False
    assert data["network_recovery"]["automatic_egress_widening_allowed"] is False
    assert all(v is False for v in data["runtime_gates"].values())

    forbidden_plan = [
        "0.0.0.0/0",
        "::/0",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "SUPABASE_ACCESS_TOKEN",
        "BEGIN PRIVATE KEY",
        "postgresql://",
        "postgres://",
    ]
    for marker in forbidden_plan:
        assert marker not in raw, f"forbidden live/secret marker in recovery plan: {marker}"

    required_validator = [
        'assert data["authorized_for_live_recovery"] is False',
        'assert all(value is False for value in data["protected_domains"].values())',
        'assert all(value is False for value in data["runtime_gates"].values())',
        "forbidden_execution_markers",
    ]
    for marker in required_validator:
        assert marker in validator, f"missing recovery validator guard: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host recovery review checks: PASS")
