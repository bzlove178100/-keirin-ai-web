"""Synthetic inventory, privacy and exact IAM-delta checks; no AWS access."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inventory", ROOT / "review/aws_lightsail_readonly_inventory.py")
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)
PRIVATE = "PRIVATE_CANARY_987654321098_203.0.113.77"


def item(name, kind):
    return {"name": name, "region": inventory.REGION, "kind": kind}


def page(*items, token=None):
    return {"items": list(items), "nextPageToken": token}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in ("AWS_REGION", "AWS_DEFAULT_REGION", "AWS_ENDPOINT_URL",
                "AWS_ENDPOINT_URL_LIGHTSAIL", "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(key, raising=False)


def install_responses(monkeypatch, responses):
    queue = list(responses)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert command[:2] == ["aws", "lightsail"]
        assert command[2] in {"get-instances", "get-static-ips", "get-key-pairs"}
        assert command[command.index("--region") + 1] == inventory.REGION
        assert "--no-paginate" in command and "--no-cli-pager" in command
        assert kwargs["env"]["AWS_MAX_ATTEMPTS"] == "1"
        assert 0 < kwargs["timeout"] <= 20
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.PIPE
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, subprocess.CompletedProcess):
            return response
        raw = response if isinstance(response, bytes) else json.dumps(response).encode()
        return subprocess.CompletedProcess(command, 0, raw, PRIVATE.encode())

    monkeypatch.setattr(inventory.subprocess, "run", run)
    return calls


def test_paginated_inventory_finds_late_collision_and_excludes_identifiers(monkeypatch, capsys):
    calls = install_responses(monkeypatch, [
        page(token=PRIVATE), page(item(inventory.INSTANCE_NAME, "Instance")),
        page(item(inventory.STATIC_IP_NAME, "StaticIp")),
        page(item(PRIVATE, "KeyPair"), token="second-key-page"),
        page(item(inventory.DEFAULT_KEY_NAME, "KeyPair")),
    ])
    assert inventory.main() == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["inventory_complete"] is True
    assert result["candidate_instance_name_exists"] is True
    assert result["candidate_static_ip_name_exists"] is True
    assert result["tokyo_default_key_present"] is True
    assert result["key_pair_count"] == 2
    assert result["authorized_for_live_create"] is False
    assert result["account_identity_independently_verified"] is False
    assert result["cloudformation_stack_inventory_checked"] is False
    assert result["key_login_verified"] is False
    assert PRIVATE not in output.out + output.err
    assert inventory.INSTANCE_NAME not in output.out
    assert inventory.DEFAULT_KEY_NAME not in output.out
    assert calls[1][-2:] == ["--page-token", PRIVATE]
    assert all("--include-default-key-pair" in call for call in calls if call[2] == "get-key-pairs")
    for call in calls:
        query = call[call.index("--query") + 1]
        assert "name:name,region:location.regionName,kind:resourceType" in query
        assert not any(field in query for field in ("arn", "ipAddress", "fingerprint", "tags"))


@pytest.mark.parametrize("has_default", [False, True])
def test_empty_inventory_is_not_live_creation_authority(monkeypatch, capsys, has_default):
    keys = page(item(inventory.DEFAULT_KEY_NAME, "KeyPair")) if has_default else page()
    install_responses(monkeypatch, [page(), page(), keys])
    assert inventory.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["instance_count"] == result["static_ip_count"] == 0
    assert result["tokyo_default_key_present"] is has_default
    assert result["authorized_for_live_create"] is False
    assert ("TOKYO_DEFAULT_KEY_NOT_OBSERVED" in result["review_reasons"]) is (not has_default)


@pytest.mark.parametrize("stage", [0, 1, 2])
def test_denied_request_has_no_partial_success_or_private_error(monkeypatch, capsys, stage):
    failure = subprocess.CompletedProcess([], 254, PRIVATE.encode(),
        ("An error occurred (AccessDeniedException) " + PRIVATE).encode())
    calls = install_responses(monkeypatch, [page()] * stage + [failure])
    assert inventory.main() == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert len(calls) == stage + 1
    assert result["inventory_complete"] is False
    assert "instance_count" not in result
    assert result["failure"]["reason"] == "access_denied"
    assert result["failure"]["operation"] == inventory.OPERATIONS[stage][0]
    assert PRIVATE not in output.out + output.err


@pytest.mark.parametrize("response", [
    b"{PRIVATE_CANARY_987654321098_203.0.113.77",
    b'{"items":[],"items":[]}', {}, {"items": None}, {"items": [None]},
    page({"name": "x", "region": "us-east-1", "kind": "Instance"}),
    page({"name": "x", "region": inventory.REGION, "kind": "KeyPair"}),
    page(item("bad\nname", "Instance")), page(token=""), page(token=7),
])
def test_incomplete_or_malformed_response_never_becomes_absence(monkeypatch, capsys, response):
    calls = install_responses(monkeypatch, [response])
    assert inventory.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["inventory_complete"] is False
    assert "instance_count" not in output.out
    assert PRIVATE not in output.out + output.err
    assert len(calls) == 1


@pytest.mark.parametrize("pages,reason", [
    ([page(token=PRIVATE), page(token=PRIVATE)], "invalid_or_repeated_page_token"),
    ([page(item("a", "Instance"), token=PRIVATE), page(item("a", "Instance"))], "invalid_or_duplicate_resource"),
    ([page(token="a"), page(token="b")], "page_limit_exceeded"),
])
def test_pagination_failure_does_not_report_partial_counts(monkeypatch, capsys, pages, reason):
    monkeypatch.setattr(inventory, "MAX_PAGES", 2)
    calls = install_responses(monkeypatch, pages)
    assert inventory.main() == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["failure"]["reason"] == reason
    assert "instance_count" not in result
    assert PRIVATE not in output.out + output.err
    assert len(calls) == 2


@pytest.mark.parametrize("failure,reason", [
    (subprocess.TimeoutExpired([PRIVATE], 20, output=PRIVATE.encode()), "request_timeout"),
    (FileNotFoundError(PRIVATE), "aws_cli_unavailable"),
    (RuntimeError(PRIVATE), "internal_error"),
])
def test_driver_failure_is_sanitized(monkeypatch, capsys, failure, reason):
    install_responses(monkeypatch, [failure])
    assert inventory.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["failure"]["reason"] == reason
    assert PRIVATE not in output.out + output.err


@pytest.mark.parametrize("key,value", [
    ("AWS_REGION", "us-east-1"), ("AWS_DEFAULT_REGION", "eu-west-1"),
    ("AWS_REGION", ""), ("AWS_ENDPOINT_URL", "https://invalid.example"),
])
def test_wrong_region_or_endpoint_stops_before_aws(monkeypatch, capsys, key, value):
    monkeypatch.setenv(key, value)
    calls = install_responses(monkeypatch, [])
    assert inventory.main() == 1
    assert not calls
    assert json.loads(capsys.readouterr().out)["inventory_complete"] is False


def test_global_deadline_stops_without_cli(monkeypatch, capsys):
    monkeypatch.setattr(inventory, "MAX_SECONDS", 0)
    calls = install_responses(monkeypatch, [])
    assert inventory.main() == 1
    assert not calls
    assert json.loads(capsys.readouterr().out)["failure"]["reason"] == "deadline_exceeded"


def test_role_update_changes_only_three_tokyo_inventory_reads():
    original = yaml.load((ROOT / "review/aws_github_oidc_readonly_role.yaml").read_text(), Loader=yaml.BaseLoader)
    candidate = yaml.load((ROOT / "review/aws_lightsail_inventory_role_update.yaml").read_text(), Loader=yaml.BaseLoader)
    restored = copy.deepcopy(candidate)
    statements = restored["Resources"]["GitHubLightsailReadOnlyRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    added = statements.pop()
    assert added == {
        "Sid": "ReadOnlyTokyoInventory", "Effect": "Allow", "Resource": "*",
        "Action": ["lightsail:GetInstances", "lightsail:GetStaticIps", "lightsail:GetKeyPairs"],
        "Condition": {"StringEquals": {"aws:RequestedRegion": "ap-northeast-1"}},
    }
    assert restored == original


def test_live_workflow_is_manual_approval_gated_main_only():
    workflow = yaml.load((ROOT / ".github/workflows/aws-lightsail-readonly-inventory.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert inputs["inventory_update_approved"]["default"] == "false"
    job = workflow["jobs"]["inventory"]
    assert job["if"] == "inputs.inventory_update_approved == true && github.ref == 'refs/heads/main'"
    credentials = next(step for step in job["steps"] if "configure-aws-credentials" in step.get("uses", ""))
    assert credentials["with"]["mask-aws-account-id"] == "true"
    assert credentials["with"]["role-to-assume"] == "${{ secrets.AWS_READONLY_ROLE_ARN }}"
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
