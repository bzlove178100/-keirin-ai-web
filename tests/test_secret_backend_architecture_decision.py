from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "SECRET_BACKEND_ARCHITECTURE_DECISION.md"


def normalized(text: str) -> str:
    text = text.lower().replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    require(DECISION.is_file(), "secret_backend_architecture_decision_missing")
    text = normalized(DECISION.read_text(encoding="utf-8"))

    required = (
        "separately isolated supabase project",
        "data api disabled",
        "no runtime service key",
        "direct postgresql only",
        "network restriction",
        "ssl enforced",
        "bootstrap custody separated",
        "no implicit failover to shared staging vault",
        "no automatic activation",
        "no project is created until that provisioning/cost boundary is explicitly approved",
        "real provider refresh exchange",
        "hosted execution",
        "production prediction",
    )
    for marker in required:
        require(marker in text, f"architecture_marker_missing:{marker}")

    require(
        "do not store real agent refresh credentials in the shared vault" in text,
        "shared_vault_block_missing",
    )
    require(
        "does not authorize any of the following" in text,
        "non_authorization_boundary_missing",
    )
    require(
        "creating a new supabase project or branch" in text,
        "project_creation_boundary_missing",
    )
    require(
        "changing keirin-ai-staging vault grants" in text,
        "shared_vault_mutation_boundary_missing",
    )

    print("secret_backend_architecture_decision: ok")


if __name__ == "__main__":
    main()
