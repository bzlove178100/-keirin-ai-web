#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION-ap-northeast-1}"
if [[ "$REGION" != "ap-northeast-1" ]]; then
  echo "FAIL: observation requires Tokyo ap-northeast-1" >&2
  exit 1
fi
EXPECTED_CPU=2
EXPECTED_RAM=1.0
EXPECTED_DISK=40
EXPECTED_TRANSFER=2048
MAX_PRICE_USD=7.0

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

aws lightsail get-regions \
  --include-availability-zones \
  --region "$REGION" \
  --output json \
  --no-cli-pager > "$tmp_dir/regions.json"

aws lightsail get-blueprints \
  --region "$REGION" \
  --output json \
  --no-cli-pager > "$tmp_dir/blueprints.json"

aws lightsail get-bundles \
  --region "$REGION" \
  --output json \
  --no-cli-pager > "$tmp_dir/bundles.json"

python3 - "$REGION" "$EXPECTED_CPU" "$EXPECTED_RAM" "$EXPECTED_DISK" "$EXPECTED_TRANSFER" "$MAX_PRICE_USD" \
  "$tmp_dir/regions.json" "$tmp_dir/blueprints.json" "$tmp_dir/bundles.json" <<'PY'
import json
import math
import re
import sys

(
    _,
    region,
    expected_cpu,
    expected_ram,
    expected_disk,
    expected_transfer,
    max_price,
    regions_path,
    blueprints_path,
    bundles_path,
) = sys.argv

expected_cpu = int(expected_cpu)
expected_ram = float(expected_ram)
expected_disk = int(expected_disk)
expected_transfer = int(expected_transfer)
max_price = float(max_price)


def catalog_items(document, key):
    if not isinstance(document, dict) or not isinstance(document.get(key), list):
        raise SystemExit("FAIL: malformed catalog response")
    items = document[key]
    if any(not isinstance(item, dict) for item in items):
        raise SystemExit("FAIL: malformed catalog entry")
    return items


def number(value):
    if type(value) not in (int, float):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is not None

with open(regions_path, encoding="utf-8") as fh:
    regions_doc = json.load(fh)
with open(blueprints_path, encoding="utf-8") as fh:
    blueprints_doc = json.load(fh)
with open(bundles_path, encoding="utf-8") as fh:
    bundles_doc = json.load(fh)

regions = [
    item for item in catalog_items(regions_doc, "regions")
    if item.get("name") == region
]
if not regions:
    raise SystemExit(f"FAIL: Lightsail region {region} was not returned")

ubuntu = []
for item in catalog_items(blueprints_doc, "blueprints"):
    if item.get("platform") != "LINUX_UNIX":
        continue
    if item.get("isActive") is not True:
        continue
    if item.get("type") != "os" or not identifier(item.get("blueprintId")):
        continue
    name = str(item.get("name", ""))
    description = str(item.get("description", ""))
    if "ubuntu" not in (name + " " + description).lower():
        continue
    if not re.search(r"\bLTS\b", name + " " + description + " " + str(item.get("version", "")), re.IGNORECASE):
        continue
    ubuntu.append({
        "blueprintId": item.get("blueprintId"),
        "name": item.get("name"),
        "version": item.get("version"),
        "isActive": item.get("isActive"),
    })

if not ubuntu:
    raise SystemExit("FAIL: no active Ubuntu Linux/Unix blueprint was returned")

candidates = []
for item in catalog_items(bundles_doc, "bundles"):
    if item.get("isActive") is not True or not identifier(item.get("bundleId")):
        continue
    platforms = item.get("supportedPlatforms")
    if not isinstance(platforms, list) or "LINUX_UNIX" not in platforms:
        continue
    if number(item.get("cpuCount")) != expected_cpu:
        continue
    if number(item.get("ramSizeInGb")) != expected_ram:
        continue
    if number(item.get("diskSizeInGb")) != expected_disk:
        continue
    if number(item.get("transferPerMonthInGb")) != expected_transfer:
        continue
    if number(item.get("publicIpv4AddressCount")) != 1:
        continue
    price = number(item.get("price"))
    if price is None or price > max_price:
        continue
    candidates.append({
        "bundleId": item.get("bundleId"),
        "name": item.get("name"),
        "priceUSD": price,
        "cpuCount": item.get("cpuCount"),
        "ramSizeInGb": item.get("ramSizeInGb"),
        "diskSizeInGb": item.get("diskSizeInGb"),
        "transferPerMonthInGb": item.get("transferPerMonthInGb"),
        "publicIpv4AddressCount": item.get("publicIpv4AddressCount"),
        "supportedPlatforms": platforms,
    })

if not candidates:
    raise SystemExit(
        "FAIL: no active Lightsail bundle matched "
        "2 vCPU / 1 GiB / 40 GiB / 2048 GiB transfer / <= USD 7"
    )

azs = [
    az.get("zoneName")
    for az in regions[0].get("availabilityZones", [])
    if az.get("zoneName")
]

result = {
    "observation_version": 1,
    "region": region,
    "region_available": True,
    "availability_zones": azs,
    "active_ubuntu_blueprints": ubuntu,
    "matching_bundles": candidates,
    "static_ipv4": {
        "live_allocation_test_performed": False,
        "reason": "read-only observation forbids AllocateStaticIp",
    },
    "authorized_for_live_create": False,
}
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
PY
