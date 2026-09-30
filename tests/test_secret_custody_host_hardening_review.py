from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_HOST_HARDENING_REVIEW.md"
PREFLIGHT = ROOT / "review/lightsail_host_preflight.sh"


def main():
    doc = DOC.read_text(encoding="utf-8")
    script = PREFLIGHT.read_text(encoding="utf-8")

    required_doc = [
        "review only — no host exists and nothing in this package is authorized to mutate a live machine",
        "untrusted / no-secret",
        "Do not add a swap file",
        "default deny",
        "TLS `verify-full`",
        "no kernel OOM kill",
        "Data API confirmed disabled",
        "Postgres SSL enforcement confirmed enabled",
        "C2 DDL receives separate explicit authorization",
        "does not authorize AWS provisioning or charges",
    ]
    for marker in required_doc:
        assert marker in doc, f"missing hardening-review marker: {marker}"

    required_script = [
        "REVIEW-ONLY READ-ONLY PREFLIGHT",
        "RESULT PREFLIGHT_OK_NO_MUTATION",
        "cgroup:v2",
        "memory:reviewed_1gb_class_floor",
        "swap:disabled",
        "listeners:no_unexpected_wildcard_except_bootstrap_ssh",
    ]
    for marker in required_script:
        assert marker in script, f"missing read-only preflight marker: {marker}"

    forbidden_script = [
        "curl ",
        "wget ",
        "apt ",
        "apt-get ",
        "dnf ",
        "yum ",
        "apk ",
        "nft add",
        "nft delete",
        "nft flush",
        "iptables ",
        "systemctl restart",
        "systemctl enable",
        "systemctl disable",
        "sysctl -w",
        "swapoff",
        "swapon",
        "chmod ",
        "chown ",
        "useradd ",
        "usermod ",
        "groupadd ",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "SUPABASE_ACCESS_TOKEN",
    ]
    for marker in forbidden_script:
        assert marker not in script, f"mutating/network/secret marker in read-only preflight: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host hardening review checks: PASS")
