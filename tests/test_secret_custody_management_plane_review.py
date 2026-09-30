from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "SECRET_CUSTODY_MANAGEMENT_PLANE_PREFLIGHT.md"


def main():
    text = DOC.read_text(encoding="utf-8")

    required = [
        "review only — no management-plane mutation is authorized by this file",
        "Data API disabled",
        "Postgres SSL enforcement enabled",
        "database/pooler network restrictions limited to the approved hardened-host CIDR set",
        "GET /v1/projects/{ref}/postgrest",
        "GET /v1/projects/{ref}/ssl-enforcement",
        "GET /v1/projects/{ref}/network-restrictions",
        "sslmode=verify-full",
        "do not change network restrictions until the hardened-host egress CIDR set is known",
        "A guessed CIDR can",
        "separate explicit C2 DDL authorization",
        "No C2 schema apply",
    ]
    for marker in required:
        assert marker in text, f"missing management-plane safety marker: {marker}"

    forbidden = [
        "SUPABASE_ACCESS_TOKEN=",
        "sbp_",
        "0.0.0.0/0",
        "::/0",
        "PATCH /v1/projects/{ref}/postgrest",
        "PUT /v1/projects/{ref}/ssl-enforcement",
        "/network-restrictions/apply",
    ]
    for marker in forbidden:
        assert marker not in text, f"unsafe live-management marker present: {marker}"


if __name__ == "__main__":
    main()
    print("secret-custody management-plane review checks: PASS")
