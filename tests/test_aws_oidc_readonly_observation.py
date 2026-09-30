from pathlib import Path
import re

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
