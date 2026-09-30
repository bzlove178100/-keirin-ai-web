import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("lightsail_control_plane_observation.template.json")


def main():
    raw = TEMPLATE.read_text(encoding="utf-8")
    data = json.loads(raw)

    assert data["schema_version"] == "lightsail-control-plane-observation-v1"
    assert data["status"] == "review_only"
    assert data["observation_only"] is True
    assert data["authorized_for_live_create"] is False

    expected = data["expected"]
    assert expected["provider"] == "amazon_lightsail"
    assert expected["region"] == "ap-northeast-1"
    assert expected["os_family"] == "linux_unix"
    assert expected["preferred_blueprint_family"] == "ubuntu_lts"
    assert expected["vcpus"] == 2
    assert expected["memory_gib"] == 1
    assert expected["storage_gib"] == 40
    assert expected["transfer_tb"] == 2
    assert expected["max_monthly_usd"] == 7
    assert expected["static_ipv4_required"] is True
    assert expected["automatic_region_substitution_allowed"] is False
    assert expected["automatic_size_substitution_allowed"] is False

    assert all(value is None for value in data["observed"].values())

    acceptance = data["acceptance"]
    assert acceptance["all_values_must_be_directly_observed"] is True
    assert acceptance["unknown_or_ambiguous_fails_closed"] is True
    assert acceptance["exact_shape_match_required"] is True
    assert acceptance["price_must_not_exceed_expected_max"] is True
    assert acceptance["separate_live_provision_authorization_required"] is True

    assert all(value is False for value in data["sensitive_data_policy"].values())
    assert all(value is False for value in data["runtime_gates"].values())

    forbidden_literals = [
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
    for marker in forbidden_literals:
        assert marker not in raw, f"forbidden secret/network literal in observation template: {marker}"

    forbidden_execution_markers = [
        "create-instances",
        "delete-instance",
        "reboot-instance",
        "stop-instance",
        "start-instance",
        "allocate-static-ip",
        "attach-static-ip",
        "release-static-ip",
        "put-instance-public-ports",
        "open-instance-public-ports",
        "close-instance-public-ports",
        "create-disk",
        "create-load-balancer",
        "create-relational-database",
        "aws lightsail",
        "curl ",
        "wget ",
    ]
    for marker in forbidden_execution_markers:
        assert marker not in raw, f"AWS/network mutation marker in observation template: {marker}"


if __name__ == "__main__":
    main()
    print("lightsail control-plane observation template validation: PASS")
