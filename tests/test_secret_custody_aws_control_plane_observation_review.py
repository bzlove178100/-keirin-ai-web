import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_AWS_CONTROL_PLANE_OBSERVATION_REVIEW.md"
TEMPLATE = ROOT / "review/lightsail_control_plane_observation.template.json"
VALIDATOR = ROOT / "review/validate_lightsail_control_plane_observation.py"


def main():
    doc = DOC.read_text(encoding="utf-8")
    raw = TEMPLATE.read_text(encoding="utf-8")
    data = json.loads(raw)
    validator = VALIDATOR.read_text(encoding="utf-8")

    required_doc = [
        "observation does not authorize AWS resource creation or mutation",
        "exact control-plane blueprint identifier",
        "displayed monthly bundle price does not exceed USD 7",
        "Unknown, unavailable, ambiguous or conflicting values fail closed",
        "requires a separate explicit live-provision instruction",
        "does not authorize or perform AWS provisioning",
    ]
    for marker in required_doc:
        assert marker in doc, f"missing AWS observation review marker: {marker}"

    assert data["status"] == "review_only"
    assert data["observation_only"] is True
    assert data["authorized_for_live_create"] is False
    assert data["expected"]["region"] == "ap-northeast-1"
    assert data["expected"]["max_monthly_usd"] == 7
    assert data["expected"]["automatic_region_substitution_allowed"] is False
    assert data["expected"]["automatic_size_substitution_allowed"] is False
    assert all(v is None for v in data["observed"].values())
    assert all(v is False for v in data["sensitive_data_policy"].values())
    assert all(v is False for v in data["runtime_gates"].values())

    forbidden_template = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "SUPABASE_ACCESS_TOKEN",
        "BEGIN PRIVATE KEY",
        "postgresql://",
        "postgres://",
        "0.0.0.0/0",
        "::/0",
    ]
    for marker in forbidden_template:
        assert marker not in raw, f"forbidden live/secret marker in AWS observation template: {marker}"

    required_validator = [
        'assert data["authorized_for_live_create"] is False',
        'assert all(value is None for value in data["observed"].values())',
        'assert all(value is False for value in data["sensitive_data_policy"].values())',
        'assert all(value is False for value in data["runtime_gates"].values())',
        "forbidden_execution_markers",
    ]
    for marker in required_validator:
        assert marker in validator, f"missing AWS observation validator guard: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody AWS control-plane observation review checks: PASS")
