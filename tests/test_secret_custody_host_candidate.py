from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_HOST_CANDIDATE.md"


def main():
    text = DOC.read_text(encoding="utf-8")

    required = [
        "candidate selected for later qualification — no host provisioned and no cost incurred",
        "Amazon Lightsail, Asia Pacific (Tokyo), Linux/Unix Micro 1 GB with public IPv4",
        "USD 7/month maximum bundle price",
        "attached Lightsail static IPv4: no additional charge",
        "do **not** weaken safeguards",
        "default-deny outbound at the host firewall",
        "TLS `verify-full`",
        "static egress IPv4 is observed as expected",
        "host egress rules block unapproved destinations",
        "No AWS account, instance, static IP, SSH key, IAM credential",
        "does not authorize",
    ]
    for marker in required:
        assert marker in text, f"missing host-candidate safety marker: {marker}"

    forbidden = [
        "0.0.0.0/0",
        "::/0",
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "SUPABASE_ACCESS_TOKEN=",
        "BEGIN PRIVATE KEY",
    ]
    for marker in forbidden:
        assert marker not in text, f"unsafe host-candidate marker present: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody host candidate checks: PASS")
