import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ml.keirin_dev_deployment_package import prepare, verify


def digest(data):
    return hashlib.sha256(data).hexdigest()


class DeploymentPackageTests(unittest.TestCase):
    def git(self, repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def write(self, root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def make_repo(self, root):
        repo = root / "repo"
        repo.mkdir()
        self.git(repo, "init")
        self.git(repo, "config", "user.email", "tests@example.invalid")
        self.git(repo, "config", "user.name", "tests")
        rollback_files = {
            "supabase/functions/predict-engine-dev/index.ts": "Deno.serve(() => new Response('old'));\n",
            "supabase/functions/predict-engine-dev/engine_phase32.ts": "export const OLD=1;\n",
            "supabase/functions/predict-engine-dev/race_data_contract.ts": "export const OLD=1;\n",
            "supabase/functions/predict-engine-dev/data_source_contract.ts": "export const OLD=1;\n",
            "supabase/functions/predict-engine-dev/persistence_contract.ts": "export const OLD=1;\n",
            "supabase/functions/history-builder-dev/index.ts": "Deno.serve(() => new Response('old history'));\n",
            "supabase/functions/backtest-engine-dev/index.ts": "Deno.serve(() => new Response('old backtest'));\n",
            "supabase/functions/_shared/race_probability.ts": "export const fullProbabilityInput=()=>true;\n",
        }
        for name, content in rollback_files.items():
            self.write(repo, name, content)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "rollback")
        rollback_commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        candidate_files = {
            "supabase/functions/predict-engine-dev/index.ts": "const p:any={}; if(p?.role!=='owner'||p?.plan!=='owner') throw Error();\n",
            "supabase/functions/predict-engine-dev/engine_phase32.ts": "export const NEW=1;\n",
            "supabase/functions/predict-engine-dev/race_data_contract.ts": "export const NEW=1;\n",
            "supabase/functions/predict-engine-dev/data_source_contract.ts": "export const PRODUCTION_DATA_SOURCE_CONNECTED=false; export const DATA_SOURCE_MODE='caller_supplied_only';\n",
            "supabase/functions/predict-engine-dev/persistence_contract.ts": "export const DB_WRITE_ENABLED=false;\n",
            "supabase/functions/predict-engine-dev/model_preview.ts": "export const result={saved:false};\n",
            "supabase/functions/predict-engine-dev/synthetic_model_views.ts": "export const SYNTHETIC_MODEL_VIEWS: unknown = null;\n",
            "model-web-response.js": "globalThis.test=true;\n",
            "supabase/functions/history-builder-dev/index.ts": "const status={db_write_enabled:false,external_fetch_enabled:false,saved:false};\n",
            "supabase/functions/backtest-engine-dev/index.ts": "const status={db_write_enabled:false,saved:false};\n",
        }
        for name, content in candidate_files.items():
            self.write(repo, name, content)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "candidate")
        return repo, rollback_commit, rollback_files

    def make_owner_package(self, root):
        package = root / "owner"
        snapshots = [
            {"rider_count": 7, "snapshot_id": "synthetic-7", "snapshot_sha256": "7" * 64, "model_artifact_sha256": "a" * 64},
            {"rider_count": 9, "snapshot_id": "synthetic-9", "snapshot_sha256": "9" * 64, "model_artifact_sha256": "a" * 64},
        ]
        views = [
            {key: item[key] for key in ("snapshot_id", "snapshot_sha256", "model_artifact_sha256")}
            | {"quality": {"rider_count": item["rider_count"]}}
            for item in snapshots
        ]
        bundle = ("export const SYNTHETIC_MODEL_VIEWS: unknown = " + json.dumps({"views": views}, separators=(",", ":")) + ";\n").encode()
        self.write(package, "bundle/synthetic_model_views.ts", bundle.decode())
        manifest = {
            "schema_version": "keirin-owner-review-package-v1",
            "synthetic_only": True,
            "deployed": False,
            "real_auth_verified": False,
            "snapshots": snapshots,
            "files": {"bundle/synthetic_model_views.ts": digest(bundle)},
        }
        self.write(package, "package.json", json.dumps(manifest))
        return package

    def make_observation(self, root, rollback_files):
        observation = root / "observation"
        mapping = {
            "predict-engine-dev": [
                "index.ts", "engine_phase32.ts", "race_data_contract.ts",
                "data_source_contract.ts", "persistence_contract.ts",
            ],
            "history-builder-dev": ["index.ts"],
            "backtest-engine-dev": ["index.ts"],
        }
        targets = {}
        versions = {"predict-engine-dev": 16, "history-builder-dev": 6, "backtest-engine-dev": 5}
        for slug, names in mapping.items():
            observed_files = {}
            for name in names:
                logical = f"supabase/functions/{slug}/{name}"
                data = rollback_files[logical].encode()
                self.write(observation, f"{slug}/{name}", data.decode())
                observed_files[logical] = digest(data)
            targets[slug] = {
                "version": versions[slug], "status": "ACTIVE", "verify_jwt": True,
                "observed_files": observed_files,
            }
        metadata = {
            "schema_version": "keirin-deployed-source-observation-v1",
            "project_id": "synthetic-project",
            "project_name": "synthetic-staging",
            "created_at": "2026-10-17T14:00:00Z",
            "targets": targets,
        }
        self.write(observation, "observation.json", json.dumps(metadata))
        return observation

    def test_prepare_move_verify_diff_and_damage_refusal(self):
        with TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            repo, rollback_commit, rollback_files = self.make_repo(root)
            owner = self.make_owner_package(root)
            observation = self.make_observation(root, rollback_files)
            output = root / "prepared"
            result = prepare(
                output, owner_package=owner, observation_dir=observation,
                rollback_commit=rollback_commit, source_root=repo,
            )
            self.assertTrue(result["prepared_only"])
            self.assertFalse(result["deployed"])
            self.assertEqual(result["deployment_order"], [
                "backtest-engine-dev", "history-builder-dev", "predict-engine-dev",
            ])
            predict = result["targets"]["predict-engine-dev"]
            self.assertTrue(predict["verify_jwt"])
            self.assertEqual(predict["observed_version"], 16)
            self.assertIn(
                "supabase/functions/predict-engine-dev/model_preview.ts",
                predict["difference"]["added"],
            )
            self.assertEqual([x["rider_count"] for x in result["snapshots"]], [7, 9])
            with self.assertRaises(FileExistsError):
                prepare(
                    output, owner_package=owner, observation_dir=observation,
                    rollback_commit=rollback_commit, source_root=repo,
                )
            moved = root / "moved"
            shutil.copytree(output, moved)
            shutil.rmtree(output)
            self.assertEqual(verify(moved), result)
            target = moved / "candidate/supabase/functions/backtest-engine-dev/index.ts"
            target.write_bytes(target.read_bytes() + b"damage")
            with self.assertRaisesRegex(ValueError, "digest_mismatch"):
                verify(moved)

    def test_rejects_observation_drift_owner_damage_and_safety_regression(self):
        with TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            repo, rollback_commit, rollback_files = self.make_repo(root)
            owner = self.make_owner_package(root)
            observation = self.make_observation(root, rollback_files)
            observed = observation / "predict-engine-dev/index.ts"
            observed.write_text("changed")
            with self.assertRaisesRegex(ValueError, "observation_digest_mismatch"):
                prepare(
                    root / "bad-observation", owner_package=owner,
                    observation_dir=observation, rollback_commit=rollback_commit,
                    source_root=repo,
                )
            observation = self.make_observation(root / "fresh", rollback_files)
            bundle = owner / "bundle/synthetic_model_views.ts"
            bundle.write_bytes(bundle.read_bytes() + b"damage")
            with self.assertRaisesRegex(ValueError, "owner_package_bundle_digest_mismatch"):
                prepare(
                    root / "bad-owner", owner_package=owner,
                    observation_dir=observation, rollback_commit=rollback_commit,
                    source_root=repo,
                )
            owner = self.make_owner_package(root / "fresh-owner")
            self.write(
                repo, "supabase/functions/predict-engine-dev/persistence_contract.ts",
                "export const DB_WRITE_ENABLED=true;\n",
            )
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "unsafe")
            with self.assertRaisesRegex(ValueError, "candidate_safety_contract_failed"):
                prepare(
                    root / "unsafe", owner_package=owner,
                    observation_dir=observation, rollback_commit=rollback_commit,
                    source_root=repo,
                )


if __name__ == "__main__":
    unittest.main()
