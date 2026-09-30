import json
from pathlib import Path

PLAN = Path(__file__).with_name("secret_custody_host_hardening.plan.json")


def main():
    raw = PLAN.read_text(encoding="utf-8")
    data = json.loads(raw)

    assert data["schema_version"] == "secret-custody-host-hardening-plan-v1"
    assert data["status"] == "review_only"
    assert data["authorized_for_live_apply"] is False

    target = data["target"]
    assert target["provider"] == "amazon_lightsail"
    assert target["region"] == "ap-northeast-1"
    assert target["memory_gib"] == 1
    assert target["vcpus"] == 2
    assert target["storage_gib"] == 40
    assert target["transfer_tb"] == 2
    assert target["max_monthly_usd"] == 7
    assert target["static_ipv4_required"] is True
    assert target["automatic_resize_allowed"] is False
    assert target["region_substitution_allowed"] is False

    assert data["preconditions"]["host_still_no_secret"] is True
    assert data["preconditions"]["swap_must_be_disabled"] is True
    assert data["preconditions"]["unexpected_wildcard_listener_allowed"] is False

    assert data["network"]["runtime_default_deny_egress_required"] is True
    assert data["network"]["world_open_ipv4_allowed"] is False
    assert data["network"]["world_open_ipv6_allowed"] is False

    assert all(value is False for value in data["runtime_gates"].values())
    assert all(value is False for value in data["secret_policy"].values())

    rollback = data["rollback"]
    assert rollback["valid_only_before_real_credential_or_c2_binding"] is True
    assert rollback["runtime_must_remain_disabled"] is True
    assert rollback["require_no_active_runtime_process"] is True
    assert rollback["must_not_touch_supabase_schema_or_vault"] is True
    assert rollback["must_not_touch_prediction_or_race_data"] is True

    forbidden_literals = [
        "0.0.0.0/0",
        "::/0",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "SUPABASE_ACCESS_TOKEN",
        "BEGIN PRIVATE KEY",
        "postgresql://",
        "postgres://",
    ]
    for marker in forbidden_literals:
        assert marker not in raw, f"forbidden live/secret literal in hardening plan: {marker}"

    forbidden_execution_markers = [
        "apt-get ",
        "apt ",
        "dnf ",
        "yum ",
        "nft add",
        "nft delete",
        "nft flush",
        "iptables ",
        "systemctl enable",
        "systemctl restart",
        "useradd ",
        "usermod ",
        "groupadd ",
        "chmod ",
        "chown ",
        "curl ",
        "wget ",
    ]
    for marker in forbidden_execution_markers:
        assert marker not in raw, f"executable mutation marker in plan data: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host hardening plan validation: PASS")
