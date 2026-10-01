#!/usr/bin/env python3
"""Read-only, bounded Tokyo inventory. Never print raw service data or errors."""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

REGION = "ap-northeast-1"
INSTANCE_NAME = "keirin-custody-h1"
STATIC_IP_NAME = "keirin-custody-h1-ip"
DEFAULT_KEY_NAME = "LightsailDefaultKey-ap-northeast-1"
MAX_PAGES = 20
MAX_SECONDS = 120
OPERATIONS = (
    ("get-instances", "instances", "Instance"),
    ("get-static-ips", "staticIps", "StaticIp"),
    ("get-key-pairs", "keyPairs", "KeyPair"),
)


class InventoryError(Exception):
    def __init__(self, operation, reason, exit_code=None):
        self.operation = operation
        self.reason = reason
        self.exit_code = exit_code


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_names(operation, collection, resource_type, deadline):
    names, tokens = set(), set()
    token = None
    for _ in range(MAX_PAGES):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise InventoryError(operation, "deadline_exceeded")
        # Projection drops addresses, ARNs, fingerprints, tags and account data.
        query = ("{items:" + collection +
                 "[].{name:name,region:location.regionName,kind:resourceType},"
                 "nextPageToken:nextPageToken}")
        command = ["aws", "lightsail", operation, "--region", REGION,
                   "--no-paginate", "--output", "json", "--no-cli-pager",
                   "--query", query, "--cli-connect-timeout", "5",
                   "--cli-read-timeout", "15"]
        if operation == "get-key-pairs":
            command.append("--include-default-key-pair")
        if token is not None:
            command.extend(["--page-token", token])
        env = dict(os.environ, AWS_MAX_ATTEMPTS="1", AWS_RETRY_MODE="standard",
                   AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off")
        try:
            response = subprocess.run(command, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, env=env,
                                      timeout=min(20, remaining), check=False)
        except subprocess.TimeoutExpired:
            raise InventoryError(operation, "request_timeout") from None
        except OSError:
            raise InventoryError(operation, "aws_cli_unavailable") from None
        if response.returncode:
            reason = "aws_cli_failure"
            # Return only allowlisted classifications, never raw AWS error text.
            if re.search(rb"\((AccessDenied|AccessDeniedException|UnauthorizedOperation)\)", response.stderr):
                reason = "access_denied"
            elif re.search(rb"\((AccountSetupInProgressException|RegionSetupInProgressException)\)", response.stderr):
                reason = "account_or_region_setup_incomplete"
            raise InventoryError(operation, reason, response.returncode)
        if len(response.stdout) > 2_000_000:
            raise InventoryError(operation, "response_too_large")
        try:
            data = json.loads(response.stdout, object_pairs_hook=reject_duplicate_keys)
        except (ValueError, UnicodeError, RecursionError):
            raise InventoryError(operation, "malformed_response") from None
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise InventoryError(operation, "malformed_response")
        for item in data["items"]:
            if (not isinstance(item, dict)
                    or not isinstance(item.get("name"), str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", item["name"])
                    or item.get("region") != REGION
                    or item.get("kind") != resource_type
                    or item["name"] in names):
                raise InventoryError(operation, "invalid_or_duplicate_resource")
            names.add(item["name"])
        next_token = data.get("nextPageToken")
        if next_token is None:
            return names
        if not isinstance(next_token, str) or not next_token or len(next_token) > 8192 or next_token in tokens:
            raise InventoryError(operation, "invalid_or_repeated_page_token")
        tokens.add(next_token)
        token = next_token
    raise InventoryError(operation, "page_limit_exceeded")


def observe():
    if (os.environ.get("AWS_REGION", REGION) != REGION
            or os.environ.get("AWS_DEFAULT_REGION", REGION) != REGION):
        raise InventoryError("preflight", "tokyo_required")
    if any(os.environ.get(key) for key in ("AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_LIGHTSAIL")):
        raise InventoryError("preflight", "endpoint_override_not_reviewed")
    deadline = time.monotonic() + MAX_SECONDS
    instances, static_ips, keys = [read_names(*operation, deadline) for operation in OPERATIONS]
    reasons = []
    if instances:
        reasons.append("EXISTING_INSTANCES_REQUIRE_REVIEW")
    if static_ips:
        reasons.append("EXISTING_STATIC_IPS_REQUIRE_REVIEW")
    if DEFAULT_KEY_NAME not in keys:
        reasons.append("TOKYO_DEFAULT_KEY_NOT_OBSERVED")
    return {
        "inventory_version": 1,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": REGION,
        "inventory_complete": True,
        "instance_count": len(instances),
        "static_ip_count": len(static_ips),
        "key_pair_count": len(keys),
        "candidate_instance_name_exists": INSTANCE_NAME in instances,
        "candidate_static_ip_name_exists": STATIC_IP_NAME in static_ips,
        "tokyo_default_key_present": DEFAULT_KEY_NAME in keys,
        "review_reasons": reasons,
        "account_identity_independently_verified": False,
        "cloudformation_stack_inventory_checked": False,
        "key_login_verified": False,
        "authorized_for_live_create": False,
    }


def main():
    try:
        result = observe()
    except InventoryError as error:
        result = {"inventory_complete": False, "authorized_for_live_create": False,
                  "failure": {"operation": error.operation, "reason": error.reason}}
        if error.exit_code is not None:
            result["failure"]["exit_code"] = error.exit_code
        print(json.dumps(result, sort_keys=True))
        return 1
    except Exception:
        # Unexpected parser/driver failures must not disclose operational data.
        print('{"inventory_complete":false,"failure":{"reason":"internal_error"},"authorized_for_live_create":false}')
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
