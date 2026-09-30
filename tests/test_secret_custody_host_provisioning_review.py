import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_HOST_PROVISIONING_REVIEW.md"
MANIFEST = ROOT / "review/lightsail_provisioning_manifest.template.json"


def main():
    doc = DOC.read_text(encoding="utf-8")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    required_doc = [
        "review only — no AWS resource creation is authorized by this file",
        "USD 7/month",
        "exactly one attached static IPv4",
        "Do not create or rotate IAM access keys",
        "no-secret first boot",
        "default-deny egress",
        "verify-full TLS",
        "authorized_for_live_create",
        "repository state alone never grants authorization",
        "does not authorize or perform AWS provisioning",
    ]
    for marker in required_doc:
        assert marker in doc, f"missing provisioning-review marker: {marker}"

    assert data["schema_version"] == "lightsail-secret-custody-provision-v1"
    assert data["status"] == "review_only"
    assert data["authorized_for_live_create"] is False
    assert data["provider"] == "amazon_lightsail"
    assert data["region"] == "ap-northeast-1"

    instance = data["instance"]
    assert instance["public_ipv4_required"] is True
    assert instance["vcpus"] == 2
    assert instance["memory_gib"] == 1
    assert instance["storage_gib"] == 40
    assert instance["transfer_tb"] == 2
    assert instance["max_monthly_usd"] == 7
    assert instance["exact_blueprint_id"] == "UNSET_LIVE_CONTROL_PLANE_VALUE"

    static_ip = data["static_ipv4"]
    assert static_ip["required"] is True
    assert static_ip["attach_immediately"] is True
    assert static_ip["address"] == "UNSET_PRIVATE_OPERATIONAL_VALUE"
    assert static_ip["commit_address_to_repository"] is False

    assert all(value is False for value in data["initial_runtime"].values())
    assert all(value is False for value in data["secret_policy"].values())
    assert all(value is True for value in data["qualification"].values())
    assert all(value is True for value in data["cost_guard"].values())

    serialized = MANIFEST.read_text(encoding="utf-8")
    forbidden = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "SUPABASE_ACCESS_TOKEN",
        "service_role",
        "refresh_token",
        "BEGIN PRIVATE KEY",
        "0.0.0.0/0",
        "::/0",
    ]
    for marker in forbidden:
        assert marker not in serialized, f"forbidden live/secret marker in provisioning manifest: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host provisioning review checks: PASS")
