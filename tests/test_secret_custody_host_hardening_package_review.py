import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_HOST_HARDENING_PACKAGE_REVIEW.md"
PLAN = ROOT / "review/secret_custody_host_hardening.plan.json"
VALIDATOR = ROOT / "review/validate_secret_custody_host_hardening_plan.py"


def main():
    doc = DOC.read_text(encoding="utf-8")
    raw = PLAN.read_text(encoding="utf-8")
    data = json.loads(raw)
    validator = VALIDATOR.read_text(encoding="utf-8")

    required_doc = [
        "review only — no live host mutation",
        "untrusted / no-secret",
        "default-deny egress",
        "NoNewPrivileges=yes",
        "ProtectSystem=strict",
        "C2 binding",
        "does not authorize or perform AWS provisioning",
    ]
    for marker in required_doc:
        assert marker in doc, f"missing hardening-package review marker: {marker}"

    assert data["status"] == "review_only"
    assert data["authorized_for_live_apply"] is False
    assert data["target"]["max_monthly_usd"] == 7
    assert data["target"]["automatic_resize_allowed"] is False
    assert data["network"]["runtime_default_deny_egress_required"] is True
    assert data["network"]["world_open_ipv4_allowed"] is False
    assert data["network"]["world_open_ipv6_allowed"] is False
    assert all(v is False for v in data["runtime_gates"].values())
    assert all(v is False for v in data["secret_policy"].values())

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
        assert marker not in raw, f"forbidden live/secret marker in hardening plan: {marker}"

    required_validator = [
        'assert data["authorized_for_live_apply"] is False',
        'assert all(value is False for value in data["runtime_gates"].values())',
        'assert all(value is False for value in data["secret_policy"].values())',
        "forbidden_execution_markers",
    ]
    for marker in required_validator:
        assert marker in validator, f"missing offline validator guard: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host hardening package review checks: PASS")
