"""Offline safety contracts for the review-only paid provisioning template."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "review/aws_lightsail_candidate.json").read_text())


def evaluate(expression, parameters):
    if not isinstance(expression, dict):
        return expression
    if set(expression) == {"Ref"}:
        return parameters[expression["Ref"]]
    if set(expression) == {"Fn::Equals"}:
        left, right = expression["Fn::Equals"]
        return evaluate(left, parameters) == evaluate(right, parameters)
    raise AssertionError("Unexpected rule expression must be reviewed")


def rules_pass(parameters):
    return all(
        evaluate(assertion["Assert"], parameters) is True
        for rule in TEMPLATE["Rules"].values()
        for assertion in rule["Assertions"]
    )


@pytest.fixture
def parameters():
    return {
        "LiveCreateAcknowledgement": "ONE_CANDIDATE_USD7_APPROVED",
        "AWS::Region": "ap-northeast-1",
        "AWS::AccountId": "111111111111",
        "ExpectedAccountId": "111111111111",
    }


def test_explicit_acknowledgement_and_matching_context_pass_only_rules(parameters):
    assert rules_pass(parameters)
    assert TEMPLATE["Metadata"]["Review"]["AuthorizedForLiveCreate"] is False


@pytest.mark.parametrize("field,value", [
    ("LiveCreateAcknowledgement", "NOT_AUTHORIZED"),
    ("LiveCreateAcknowledgement", ""),
    ("AWS::Region", "us-east-1"),
    ("AWS::Region", "eu-north-1"),
    ("AWS::AccountId", "222222222222"),
])
def test_wrong_context_or_missing_acknowledgement_rejects(parameters, field, value):
    parameters[field] = value
    assert not rules_pass(parameters)


def test_default_acknowledgement_blocks_and_existing_key_is_required(parameters):
    parameters["LiveCreateAcknowledgement"] = TEMPLATE["Parameters"]["LiveCreateAcknowledgement"]["Default"]
    assert not rules_pass(parameters)
    existing_key = TEMPLATE["Parameters"]["ExistingKeyPairName"]
    assert "Default" not in existing_key
    assert existing_key["MinLength"] >= 1
    assert TEMPLATE["Parameters"]["ExpectedAccountId"]["NoEcho"] is True


def test_only_one_fixed_candidate_and_one_attached_ip_are_present():
    resources = TEMPLATE["Resources"]
    assert set(resources) == {"CustodyCandidate", "CustodyStaticIp"}
    instance = resources["CustodyCandidate"]
    static_ip = resources["CustodyStaticIp"]
    assert instance["Type"] == "AWS::Lightsail::Instance"
    props = instance["Properties"]
    assert props["BlueprintId"] == "ubuntu_24_04"
    assert props["BundleId"] == "micro_3_0"
    assert props["AvailabilityZone"] == {"Ref": "AvailabilityZone"}
    assert all(zone.startswith("ap-northeast-1") for zone in TEMPLATE["Parameters"]["AvailabilityZone"]["AllowedValues"])
    assert props["KeyPairName"] == {"Ref": "ExistingKeyPairName"}
    assert not set(props) & {"UserData", "AddOns", "Hardware", "Location", "State"}
    assert static_ip["Type"] == "AWS::Lightsail::StaticIp"
    assert static_ip["DependsOn"] == "CustodyCandidate"
    assert static_ip["Properties"]["AttachedTo"] == props["InstanceName"]
    for resource in resources.values():
        assert resource["DeletionPolicy"] == "Retain"
        assert resource["UpdateReplacePolicy"] == "Retain"


def test_platform_ingress_is_browser_ssh_only_for_both_ip_families():
    ports = TEMPLATE["Resources"]["CustodyCandidate"]["Properties"]["Networking"]["Ports"]
    assert len(ports) == 1
    ssh = ports[0]
    assert ssh["Protocol"] == "tcp"
    assert ssh["FromPort"] == ssh["ToPort"] == 22
    assert ssh["CidrListAliases"] == ["lightsail-connect"]
    assert ssh["Cidrs"] == []
    assert ssh["Ipv6Cidrs"] == []


def test_template_exports_no_ip_key_or_account_and_stays_untrusted():
    outputs = TEMPLATE["Outputs"]
    assert set(outputs) == {"QualificationBoundary", "Region"}
    assert outputs["QualificationBoundary"]["Value"] == "UNTRUSTED_NO_SECRET_H1_REQUIRED"
    assert "Transform" not in TEMPLATE
    assert "Conditions" not in TEMPLATE
