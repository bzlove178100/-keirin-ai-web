"""Prepare and verify a review-only Supabase Edge deployment package; never deploy."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath


SCHEMA = "keirin-dev-deployment-package-v1"
OBSERVATION_SCHEMA = "keirin-deployed-source-observation-v1"
OWNER_PACKAGE_SCHEMA = "keirin-owner-review-package-v1"
REPOSITORY_PATHS = {
    "predict-engine-dev": (
        "supabase/functions/predict-engine-dev/index.ts",
        "supabase/functions/predict-engine-dev/engine_phase32.ts",
        "supabase/functions/predict-engine-dev/race_data_contract.ts",
        "supabase/functions/_shared/race_probability.ts",
        "supabase/functions/predict-engine-dev/data_source_contract.ts",
        "supabase/functions/predict-engine-dev/persistence_contract.ts",
        "supabase/functions/predict-engine-dev/model_preview.ts",
        "supabase/functions/predict-engine-dev/synthetic_model_views.ts",
        "model-web-response.js",
    ),
    "history-builder-dev": (
        "supabase/functions/history-builder-dev/index.ts",
        "supabase/functions/_shared/race_probability.ts",
    ),
    "backtest-engine-dev": (
        "supabase/functions/backtest-engine-dev/index.ts",
        "supabase/functions/_shared/race_probability.ts",
    ),
}
ENTRYPOINTS = {
    slug: f"supabase/functions/{slug}/index.ts" for slug in REPOSITORY_PATHS
}
OBSERVED_NAMES = {
    "predict-engine-dev": {
        "index.ts": "supabase/functions/predict-engine-dev/index.ts",
        "engine_phase32.ts": "supabase/functions/predict-engine-dev/engine_phase32.ts",
        "race_data_contract.ts": "supabase/functions/predict-engine-dev/race_data_contract.ts",
        "data_source_contract.ts": "supabase/functions/predict-engine-dev/data_source_contract.ts",
        "persistence_contract.ts": "supabase/functions/predict-engine-dev/persistence_contract.ts",
    },
    "history-builder-dev": {
        "index.ts": "supabase/functions/history-builder-dev/index.ts",
    },
    "backtest-engine-dev": {
        "index.ts": "supabase/functions/backtest-engine-dev/index.ts",
    },
}
BUNDLE_LOGICAL_PATH = "supabase/functions/predict-engine-dev/synthetic_model_views.ts"
BUNDLE_PACKAGE_PATH = "bundle/synthetic_model_views.ts"
MODULE_PREFIX = b"export const SYNTHETIC_MODEL_VIEWS: unknown = "


def _digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _digest(path):
    return _digest_bytes(path.read_bytes())


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"json_invalid:{path.name}") from error


def _regular_files(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("package_directory_required")
    files = set()
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("package_regular_files_required")
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    return files


def _safe_logical_path(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and str(path) == name


def _git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if proc.returncode:
        raise ValueError("git_read_failed")
    return proc.stdout


def _commit(repo, ref="HEAD"):
    value = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("git_commit_invalid")
    return value


def _git_file(repo, commit, name):
    if not _safe_logical_path(name):
        raise ValueError("logical_path_invalid")
    return _git(repo, "show", f"{commit}:{name}")


def _assert_candidate_safety(candidate):
    predict = candidate["predict-engine-dev"]
    index = predict["supabase/functions/predict-engine-dev/index.ts"].decode()
    persistence = predict[
        "supabase/functions/predict-engine-dev/persistence_contract.ts"
    ].decode()
    source = predict[
        "supabase/functions/predict-engine-dev/data_source_contract.ts"
    ].decode()
    model = predict[
        "supabase/functions/predict-engine-dev/model_preview.ts"
    ].decode()
    history = candidate["history-builder-dev"][
        "supabase/functions/history-builder-dev/index.ts"
    ].decode()
    backtest = candidate["backtest-engine-dev"][
        "supabase/functions/backtest-engine-dev/index.ts"
    ].decode()
    required = {
        "db_write_disabled": "DB_WRITE_ENABLED=false" in persistence,
        "production_source_disconnected": "PRODUCTION_DATA_SOURCE_CONNECTED=false" in source,
        "source_mode_caller_supplied_only": "DATA_SOURCE_MODE='caller_supplied_only'" in source,
        "owner_role_and_plan": "p?.role!=='owner'||p?.plan!=='owner'" in index,
        "model_never_saved": "saved:false" in model,
        "history_no_persistence": all(
            token in history for token in ("db_write_enabled:false", "external_fetch_enabled:false", "saved:false")
        ),
        "backtest_no_persistence": all(
            token in backtest for token in ("db_write_enabled:false", "saved:false")
        ),
    }
    if not all(required.values()):
        failed = ",".join(key for key, ok in required.items() if not ok)
        raise ValueError("candidate_safety_contract_failed:" + failed)
    return required


def _bundle_snapshots(bundle):
    if not bundle.startswith(MODULE_PREFIX) or not bundle.endswith(b";\n"):
        raise ValueError("owner_package_bundle_format_invalid")
    try:
        payload = json.loads(bundle[len(MODULE_PREFIX):-2])
        views = payload["views"]
        snapshots = [
            {key: view[key] for key in ("snapshot_id", "snapshot_sha256", "model_artifact_sha256")}
            | {"rider_count": view["quality"]["rider_count"]}
            for view in views
        ]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("owner_package_bundle_format_invalid") from error
    if [item["rider_count"] for item in snapshots] != [7, 9]:
        raise ValueError("owner_package_rider_counts_invalid")
    return snapshots


def _load_owner_bundle(owner_package):
    root = Path(owner_package).resolve()
    files = _regular_files(root)
    manifest = _read_json(root / "package.json")
    if (
        manifest.get("schema_version") != OWNER_PACKAGE_SCHEMA
        or manifest.get("synthetic_only") is not True
        or manifest.get("deployed") is not False
        or manifest.get("real_auth_verified") is not False
        or BUNDLE_PACKAGE_PATH not in files
    ):
        raise ValueError("owner_package_invalid")
    expected = manifest.get("files", {}).get(BUNDLE_PACKAGE_PATH)
    bundle = (root / BUNDLE_PACKAGE_PATH).read_bytes()
    if expected != _digest_bytes(bundle):
        raise ValueError("owner_package_bundle_digest_mismatch")
    snapshots = manifest.get("snapshots")
    if snapshots != _bundle_snapshots(bundle):
        raise ValueError("owner_package_snapshot_mismatch")
    return bundle, snapshots, _digest(root / "package.json")


def _load_observation(observation_dir):
    root = Path(observation_dir).resolve()
    files = _regular_files(root)
    metadata = _read_json(root / "observation.json")
    if metadata.get("schema_version") != OBSERVATION_SCHEMA:
        raise ValueError("observation_schema_invalid")
    targets = metadata.get("targets")
    if not isinstance(targets, dict) or set(targets) != set(REPOSITORY_PATHS):
        raise ValueError("observation_targets_invalid")
    observed = {}
    expected_files = {"observation.json"}
    for slug, mapping in OBSERVED_NAMES.items():
        target = targets[slug]
        if (
            target.get("status") != "ACTIVE"
            or target.get("verify_jwt") is not True
            or not isinstance(target.get("version"), int)
        ):
            raise ValueError("observation_target_state_invalid:" + slug)
        observed[slug] = {}
        for source_name, logical_name in mapping.items():
            relative = f"{slug}/{source_name}"
            expected_files.add(relative)
            data = (root / relative).read_bytes()
            observed[slug][logical_name] = data
        digests = target.get("observed_files")
        if not isinstance(digests, dict) or set(digests) != set(mapping.values()):
            raise ValueError("observation_file_manifest_invalid:" + slug)
        for logical_name, data in observed[slug].items():
            if digests[logical_name] != _digest_bytes(data):
                raise ValueError("observation_digest_mismatch:" + slug)
    if files != expected_files:
        raise ValueError("observation_file_set_mismatch")
    return metadata, observed


def capture_observation(output_dir, *, sources_json, project_id, project_name, observed_at):
    """Preserve connector-returned UTF-8 source bytes, including EOF and CRLF.

    The input is a JSON array of get_edge_function responses, not rendered code
    copied into text files. This is an offline import, not a live-source attestation.
    """
    output = Path(output_dir).resolve()
    repo = Path(__file__).resolve().parents[1]
    if output == repo or repo in output.parents:
        raise ValueError("output_must_be_outside_repository")
    if output.exists():
        raise FileExistsError(output)
    if not all(isinstance(value, str) and value.strip() for value in
               (project_id, project_name, observed_at)):
        raise ValueError("observation_metadata_required")
    responses = _read_json(Path(sources_json))
    if not isinstance(responses, list) or len(responses) != len(OBSERVED_NAMES):
        raise ValueError("observation_targets_invalid")
    targets, sources = {}, {}
    for response in responses:
        if not isinstance(response, dict):
            raise ValueError("observation_target_state_invalid")
        slug = response.get("slug")
        if not isinstance(slug, str) or slug not in OBSERVED_NAMES or slug in targets:
            raise ValueError("observation_targets_invalid")
        if (response.get("status") != "ACTIVE"
                or response.get("verify_jwt") is not True
                or response.get("import_map") is not False
                or type(response.get("version")) is not int
                or response["version"] < 1):
            raise ValueError("observation_target_state_invalid:" + slug)
        files = response.get("files")
        if not isinstance(files, list) or len(files) != len(OBSERVED_NAMES[slug]):
            raise ValueError("observation_file_set_mismatch:" + slug)
        hashes = {}
        for source in files:
            if not isinstance(source, dict):
                raise ValueError("observation_source_invalid:" + slug)
            name, content = source.get("name"), source.get("content")
            if (not isinstance(name, str) or name not in OBSERVED_NAMES[slug]
                    or not isinstance(content, str) or not content):
                raise ValueError("observation_source_invalid:" + slug)
            logical = OBSERVED_NAMES[slug][name]
            if logical in hashes:
                raise ValueError("observation_source_duplicate:" + slug)
            data = content.encode("utf-8")
            hashes[logical] = _digest_bytes(data)
            sources[f"{slug}/{name}"] = data
        targets[slug] = {
            "version": response["version"], "status": "ACTIVE", "verify_jwt": True,
            "observed_files": hashes,
        }
    metadata = {
        "schema_version": OBSERVATION_SCHEMA, "project_id": project_id,
        "project_name": project_name, "created_at": observed_at, "targets": targets,
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, data in sources.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (output / "observation.json").write_text(json.dumps(metadata, indent=2) + "\n")
    _load_observation(output)
    return metadata


def _write_tree(root, side, sources):
    result = {}
    for slug, files in sources.items():
        result[slug] = {}
        for logical_name, data in files.items():
            physical = root / side / logical_name
            physical.parent.mkdir(parents=True, exist_ok=True)
            physical.write_bytes(data)
            result[slug][logical_name] = _digest_bytes(data)
    return result


def _target_diff(candidate, rollback):
    candidate_names = set(candidate)
    rollback_names = set(rollback)
    return {
        "added": sorted(candidate_names - rollback_names),
        "removed": sorted(rollback_names - candidate_names),
        "changed": sorted(
            name
            for name in candidate_names & rollback_names
            if candidate[name] != rollback[name]
        ),
        "unchanged": sorted(
            name
            for name in candidate_names & rollback_names
            if candidate[name] == rollback[name]
        ),
    }


def prepare(output_dir, *, owner_package, observation_dir, rollback_commit, source_root=None):
    repo = Path(source_root or Path(__file__).resolve().parents[1]).resolve()
    output = Path(output_dir).resolve()
    if output == repo or repo in output.parents:
        raise ValueError("output_must_be_outside_repository")
    if output.exists():
        raise FileExistsError(output)
    candidate_commit = _commit(repo)
    rollback_commit = _commit(repo, rollback_commit)
    bundle, snapshots, owner_manifest_sha256 = _load_owner_bundle(owner_package)
    observation, observed = _load_observation(observation_dir)

    candidate = {
        slug: {name: _git_file(repo, candidate_commit, name) for name in names}
        for slug, names in REPOSITORY_PATHS.items()
    }
    candidate["predict-engine-dev"][BUNDLE_LOGICAL_PATH] = bundle
    safety = _assert_candidate_safety(candidate)

    rollback = {}
    for slug, names in REPOSITORY_PATHS.items():
        rollback[slug] = {}
        for name in names:
            if name in observed[slug]:
                rollback[slug][name] = observed[slug][name]
        if ENTRYPOINTS[slug] not in rollback[slug]:
            raise ValueError("rollback_entrypoint_missing:" + slug)

    output.mkdir(parents=True, exist_ok=False)
    candidate_hashes = _write_tree(output, "candidate", candidate)
    rollback_hashes = _write_tree(output, "rollback", rollback)
    targets = {}
    for slug in REPOSITORY_PATHS:
        state = observation["targets"][slug]
        targets[slug] = {
            "verify_jwt": True,
            "entrypoint_path": ENTRYPOINTS[slug],
            "observed_version": state["version"],
            "observed_status": state["status"],
            "candidate_files": candidate_hashes[slug],
            "rollback_files": rollback_hashes[slug],
            "difference": _target_diff(candidate_hashes[slug], rollback_hashes[slug]),
        }
    manifest = {
        "schema_version": SCHEMA,
        "candidate_commit": candidate_commit,
        "rollback_commit": rollback_commit,
        "observation_project_id": observation.get("project_id"),
        "observation_project_name": observation.get("project_name"),
        "observation_created_at": observation.get("created_at"),
        "owner_package_manifest_sha256": owner_manifest_sha256,
        "synthetic_only": True,
        "prepared_only": True,
        "deployed": False,
        "real_auth_verified": False,
        "real_data_operation_verified": False,
        "safety_contracts": safety,
        "snapshots": snapshots,
        "deployment_order": ["backtest-engine-dev", "history-builder-dev", "predict-engine-dev"],
        "rollback_order": ["predict-engine-dev", "history-builder-dev", "backtest-engine-dev"],
        "targets": targets,
    }
    (output / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return verify(output)


def verify(package_dir):
    root = Path(package_dir).resolve()
    files = _regular_files(root)
    manifest = _read_json(root / "package.json")
    if (
        manifest.get("schema_version") != SCHEMA
        or manifest.get("synthetic_only") is not True
        or manifest.get("prepared_only") is not True
        or manifest.get("deployed") is not False
        or manifest.get("real_auth_verified") is not False
        or manifest.get("real_data_operation_verified") is not False
        or manifest.get("deployment_order") != ["backtest-engine-dev", "history-builder-dev", "predict-engine-dev"]
        or manifest.get("rollback_order") != ["predict-engine-dev", "history-builder-dev", "backtest-engine-dev"]
    ):
        raise ValueError("deployment_manifest_invalid")
    targets = manifest.get("targets")
    if not isinstance(targets, dict) or set(targets) != set(REPOSITORY_PATHS):
        raise ValueError("deployment_targets_invalid")
    expected = {"package.json"}
    for slug, target in targets.items():
        if target.get("verify_jwt") is not True or target.get("entrypoint_path") != ENTRYPOINTS[slug]:
            raise ValueError("deployment_target_contract_invalid:" + slug)
        for side in ("candidate", "rollback"):
            hashes = target.get(side + "_files")
            if not isinstance(hashes, dict) or ENTRYPOINTS[slug] not in hashes:
                raise ValueError("deployment_target_files_invalid:" + slug)
            for logical_name, digest in hashes.items():
                if not _safe_logical_path(logical_name) or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
                    raise ValueError("deployment_file_manifest_invalid:" + slug)
                relative = f"{side}/{logical_name}"
                expected.add(relative)
                if _digest(root / relative) != digest:
                    raise ValueError("deployment_file_digest_mismatch:" + relative)
        expected_diff = _target_diff(target["candidate_files"], target["rollback_files"])
        if target.get("difference") != expected_diff:
            raise ValueError("deployment_difference_invalid:" + slug)
    if files != expected:
        raise ValueError("deployment_file_set_mismatch")
    candidate = {
        slug: {
            name: (root / "candidate" / name).read_bytes()
            for name in target["candidate_files"]
        }
        for slug, target in targets.items()
    }
    safety = _assert_candidate_safety(candidate)
    if manifest.get("safety_contracts") != safety:
        raise ValueError("deployment_safety_contract_invalid")
    if manifest.get("snapshots") != _bundle_snapshots(candidate["predict-engine-dev"][BUNDLE_LOGICAL_PATH]):
        raise ValueError("deployment_snapshots_invalid")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--owner-package", type=Path, required=True)
    create.add_argument("--observation-dir", type=Path, required=True)
    create.add_argument("--rollback-commit", required=True)
    create.add_argument("--source-root", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("--package-dir", type=Path, required=True)
    capture = commands.add_parser("capture-observation")
    capture.add_argument("--output-dir", type=Path, required=True)
    capture.add_argument("--sources-json", type=Path, required=True)
    capture.add_argument("--project-id", required=True)
    capture.add_argument("--project-name", required=True)
    capture.add_argument("--observed-at", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(
            args.output_dir,
            owner_package=args.owner_package,
            observation_dir=args.observation_dir,
            rollback_commit=args.rollback_commit,
            source_root=args.source_root,
        )
    elif args.command == "capture-observation":
        result = capture_observation(
            args.output_dir, sources_json=args.sources_json, project_id=args.project_id,
            project_name=args.project_name, observed_at=args.observed_at,
        )
    else:
        result = verify(args.package_dir)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
