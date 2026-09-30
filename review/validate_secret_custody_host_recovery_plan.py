import json
from pathlib import Path

PLAN = Path(__file__).with_name("secret_custody_host_recovery.plan.json")


def main():
    raw = PLAN.read_text(encoding="utf-8")
    data = json.loads(raw)

    assert data["schema_version"] == "secret-custody-host-recovery-plan-v1"
    assert data["status"] == "review_only"
    assert data["authorized_for_live_recovery"] is False

    scope = data["scope"]
    assert scope["pre_real_credential_only"] is True
    assert scope["pre_c2_binding_only"] is True
    assert scope["host_must_remain_no_secret"] is True
    assert scope["runtime_must_remain_disabled"] is True
    assert scope["active_runtime_process_allowed"] is False

    assert all(value is False for value in data["protected_domains"].values())

    aws = data["aws_recovery"]
    assert aws["automatic_instance_delete_allowed"] is False
    assert aws["automatic_instance_resize_allowed"] is False
    assert aws["automatic_instance_reboot_allowed"] is False
    assert aws["automatic_snapshot_allowed"] is False
    assert aws["automatic_replacement_allowed"] is False
    assert aws["separate_live_authorization_required"] is True

    network = data["network_recovery"]
    assert network["automatic_firewall_relaxation_allowed"] is False
    assert network["automatic_egress_widening_allowed"] is False
    assert network["world_open_ipv4_allowed"] is False
    assert network["world_open_ipv6_allowed"] is False
    assert network["plaintext_database_fallback_allowed"] is False
    assert network["insecure_tls_fallback_allowed"] is False

    evidence = data["evidence"]
    assert evidence["metadata_only"] is True
    assert all(value is False for key, value in evidence.items() if key != "metadata_only")

    assert all(value is False for value in data["runtime_gates"].values())

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
        assert marker not in raw, f"forbidden live/secret literal in recovery plan: {marker}"

    forbidden_execution_markers = [
        "rm -rf",
        "mkfs",
        "shutdown ",
        "reboot ",
        "nft flush",
        "iptables ",
        "systemctl restart",
        "systemctl enable",
        "userdel ",
        "useradd ",
        "curl ",
        "wget ",
        "aws lightsail",
    ]
    for marker in forbidden_execution_markers:
        assert marker not in raw, f"executable/destructive marker in recovery plan data: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host recovery plan validation: PASS")
