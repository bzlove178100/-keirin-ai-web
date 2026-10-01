from pathlib import Path
import copy
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_aws_observation_workflow_is_manual_oidc_and_read_only():
    workflow = (ROOT / ".github/workflows/aws-lightsail-readonly-observation.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "id-token: write" in workflow
    assert "contents: read" in workflow
    assert "AWS_READONLY_ROLE_ARN" in workflow
    assert "ap-northeast-1" in workflow
    assert "pull_request" not in workflow
    assert "push:" not in workflow


def test_observation_script_only_uses_expected_lightsail_get_calls():
    script = (ROOT / "review/aws_lightsail_readonly_observation.sh").read_text()
    calls = re.findall(r"aws\s+lightsail\s+([a-z0-9-]+)", script)
    assert calls == ["get-regions", "get-blueprints", "get-bundles"]
    forbidden = (
        "allocate-static-ip",
        "attach-static-ip",
        "create-instances",
        "create-key-pair",
        "delete-instance",
        "detach-static-ip",
        "open-instance-public-ports",
        "put-instance-public-ports",
        "reboot-instance",
        "release-static-ip",
        "start-instance",
        "stop-instance",
    )
    for token in forbidden:
        assert token not in script


def test_oidc_role_permissions_are_catalog_read_only():
    template = (ROOT / "review/aws_github_oidc_readonly_role.yaml").read_text()
    for action in (
        "lightsail:GetRegions",
        "lightsail:GetBlueprints",
        "lightsail:GetBundles",
    ):
        assert action in template
    assert "sts:AssumeRoleWithWebIdentity" in template
    assert "sts.amazonaws.com" in template
    assert "Default: bzlove178100" in template
    assert "Default: '320407427'" in template
    assert "Default: -keirin-ai-web" in template
    assert "Default: '1357382962'" in template
    assert "repo:${GitHubOwner}@${GitHubOwnerId}/${GitHubRepository}@${GitHubRepositoryId}:ref:refs/heads/${GitHubBranch}" in template

    forbidden = (
        "lightsail:Allocate",
        "lightsail:Attach",
        "lightsail:Create",
        "lightsail:Delete",
        "lightsail:Detach",
        "lightsail:Open",
        "lightsail:Put",
        "lightsail:Release",
        "lightsail:Start",
        "lightsail:Stop",
        "lightsail:Update",
        "iam:CreateAccessKey",
    )
    for token in forbidden:
        assert token not in template


@pytest.fixture
def catalog():
    return {
        "get-regions": {"regions": [{"name": "ap-northeast-1", "availabilityZones": []}]},
        "get-blueprints": {"blueprints": [{
            "blueprintId": "synthetic_ubuntu_lts", "name": "Ubuntu LTS",
            "description": "Synthetic fixture only", "version": "test",
            "type": "os", "platform": "LINUX_UNIX", "isActive": True,
        }]},
        "get-bundles": {"bundles": [{
            "bundleId": "synthetic_micro", "name": "Synthetic fixture only",
            "isActive": True, "supportedPlatforms": ["LINUX_UNIX"],
            "cpuCount": 2, "ramSizeInGb": 1.0, "diskSizeInGb": 40,
            "transferPerMonthInGb": 2048, "price": 7.0,
            "publicIpv4AddressCount": 1,
        }]},
    }


def run_observation(tmp_path, catalog, region="ap-northeast-1", fail_call=""):
    fixtures = tmp_path / "catalog.json"
    fixtures.write_text(json.dumps(catalog))
    calls = tmp_path / "calls.jsonl"
    fake_aws = tmp_path / "aws"
    fake_aws.write_text(
        "#!" + sys.executable + "\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['FAKE_CALLS'], 'a') as fh:\n"
        "    fh.write(json.dumps(args) + '\\n')\n"
        "assert args[0] == 'lightsail'\n"
        "assert args[1] in ('get-regions', 'get-blueprints', 'get-bundles')\n"
        "assert args[args.index('--region') + 1] == 'ap-northeast-1'\n"
        "if args[1] == os.environ['FAKE_FAIL_CALL']:\n"
        "    print('PRIVATE_ERROR_CANARY role/session details', file=sys.stderr)\n"
        "    print('PRIVATE_RESPONSE_CANARY')\n"
        "    sys.exit(42)\n"
        "print(json.dumps(json.loads(Path(os.environ['FAKE_CATALOG']).read_text())[args[1]]))\n"
    )
    fake_aws.chmod(0o700)
    # No inherited AWS credentials/configuration; every aws invocation hits this stub.
    env = {
        "PATH": str(tmp_path) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        "AWS_REGION": region, "FAKE_CATALOG": str(fixtures),
        "FAKE_CALLS": str(calls), "FAKE_FAIL_CALL": fail_call,
    }
    result = subprocess.run(
        ["bash", str(ROOT / "review/aws_lightsail_readonly_observation.sh")],
        env=env, text=True, capture_output=True, timeout=20,
    )
    recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
    return result, recorded


def test_synthetic_catalog_passes_without_live_authorization(tmp_path, catalog):
    result, calls = run_observation(tmp_path, catalog)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["region"] == "ap-northeast-1"
    assert report["authorized_for_live_create"] is False
    assert report["static_ipv4"]["live_allocation_test_performed"] is False
    assert report["matching_bundles"][0]["priceUSD"] == 7
    assert [call[1] for call in calls] == ["get-regions", "get-blueprints", "get-bundles"]


@pytest.mark.parametrize("region", ["eu-north-1", "us-east-1", "", "ap-northeast-1\n"])
def test_wrong_region_stops_before_any_aws_call(tmp_path, catalog, region):
    result, calls = run_observation(tmp_path, catalog, region=region)
    assert result.returncode != 0
    assert result.stdout == ""
    assert calls == []


@pytest.mark.parametrize("action,key", [("get-blueprints", "blueprints"), ("get-bundles", "bundles")])
@pytest.mark.parametrize("state", [None, False, "true", 1])
def test_unknown_or_non_boolean_active_state_fails(tmp_path, catalog, action, key, state):
    catalog[action][key][0]["isActive"] = state
    result, _ = run_observation(tmp_path, catalog)
    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize("field,value", [
    ("price", None), ("price", "NaN"), ("price", float("nan")),
    ("price", float("inf")), ("price", -1), ("price", True), ("price", 7.01),
    ("price", "7"), ("ramSizeInGb", True), ("ramSizeInGb", "1"),
    ("cpuCount", 1), ("diskSizeInGb", 20), ("transferPerMonthInGb", 1024),
    ("publicIpv4AddressCount", 0), ("publicIpv4AddressCount", None),
    ("publicIpv4AddressCount", True), ("supportedPlatforms", "LINUX_UNIX"),
    ("supportedPlatforms", ["WINDOWS"]), ("bundleId", ""), ("bundleId", None),
])
def test_unknown_or_mismatched_bundle_fails(tmp_path, catalog, field, value):
    catalog["get-bundles"]["bundles"][0][field] = value
    result, _ = run_observation(tmp_path, catalog)
    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize("field,value", [
    ("name", "Ubuntu"), ("type", "app"), ("type", None),
    ("platform", "WINDOWS"), ("blueprintId", None), ("blueprintId", ""),
])
def test_unproven_ubuntu_lts_os_fails(tmp_path, catalog, field, value):
    catalog["get-blueprints"]["blueprints"][0][field] = value
    result, _ = run_observation(tmp_path, catalog)
    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize("action,key", [("get-regions", "regions"), ("get-blueprints", "blueprints"), ("get-bundles", "bundles")])
@pytest.mark.parametrize("value", [None, {}, [None], []])
def test_malformed_or_empty_catalog_fails(tmp_path, catalog, action, key, value):
    catalog[action][key] = value
    result, _ = run_observation(tmp_path, catalog)
    assert result.returncode != 0
    assert result.stdout == ""


def test_incomplete_entry_does_not_hide_valid_candidate(tmp_path, catalog):
    invalid = copy.deepcopy(catalog["get-bundles"]["bundles"][0])
    del invalid["isActive"]
    catalog["get-bundles"]["bundles"].insert(0, invalid)
    result, _ = run_observation(tmp_path, catalog)
    assert result.returncode == 0
    assert len(json.loads(result.stdout)["matching_bundles"]) == 1


@pytest.mark.parametrize("fail_call,count", [
    ("get-regions", 1), ("get-blueprints", 2), ("get-bundles", 3),
])
def test_aws_failure_stops_without_raw_error_or_success_report(tmp_path, catalog, fail_call, count):
    result, calls = run_observation(tmp_path, catalog, fail_call=fail_call)
    assert result.returncode == 42
    assert result.stdout == ""
    assert result.stderr == f"FAIL: Lightsail {fail_call} failed (exit 42); raw AWS error omitted\n"
    assert "PRIVATE_ERROR_CANARY" not in result.stdout + result.stderr
    assert "PRIVATE_RESPONSE_CANARY" not in result.stdout + result.stderr
    assert [call[1] for call in calls] == ["get-regions", "get-blueprints", "get-bundles"][:count]
