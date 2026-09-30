#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-ap-northeast-1}"
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

with open(regions_path, encoding="utf-8") as fh:
    regions_doc = json.load(fh)
with open(blueprints_path, encoding="utf-8") as fh:
    blueprints_doc = json.load(fh)
with open(bundles_path, encoding="utf-8") as fh:
    bundles_doc = json.load(fh)

regions = [
    item for item in regions_doc.get("regions", [])
    if item.get("name") == region
]
if not regions:
    raise SystemExit(f"FAIL: Lightsail region {region} was not returned")

ubuntu = []
for item in blueprints_doc.get("blueprints", []):
    if item.get("platform") != "LINUX_UNIX":
        continue
    if item.get("isActive") is False:
        continue
    name = str(item.get("name", ""))
    description = str(item.get("description", ""))
    if "ubuntu" not in (name + " " + description).lower():
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
for item in bundles_doc.get("bundles", []):
    if item.get("isActive") is False:
        continue
    platforms = item.get("supportedPlatforms") or []
    if "LINUX_UNIX" not in platforms:
        continue
    if item.get("cpuCount") != expected_cpu:
        continue
    if float(item.get("ramSizeInGb", -1)) != expected_ram:
        continue
    if item.get("diskSizeInGb") != expected_disk:
        continue
    if item.get("transferPerMonthInGb") != expected_transfer:
        continue
    price = float(item.get("price", 1e9))
    if price > max_price:
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
