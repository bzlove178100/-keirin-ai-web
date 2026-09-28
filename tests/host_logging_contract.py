"""Synthetic Docker log-driver controls; not a platform/database logging audit."""
import json
import subprocess
from uuid import uuid4

from run_host_limits_contract import command, create_args, verify_config
from support.log_output_probe import STDOUT_MARKER, STDERR_MARKER


def verify_log_evidence(driver, log_path, result):
    lines = result.stdout.splitlines() + result.stderr.splitlines()
    if driver == "json-file":
        if (not log_path or result.returncode != 0 or len(lines) != 2
                or set(lines) != {STDOUT_MARKER, STDERR_MARKER}):
            raise RuntimeError("synthetic_log_positive_control_failed")
    elif driver == "none":
        if log_path or STDOUT_MARKER in result.stdout + result.stderr or STDERR_MARKER in result.stdout + result.stderr:
            raise RuntimeError("synthetic_log_persistence_detected")
        if result.returncode == 0 and not result.stdout.strip() and not result.stderr.strip():
            return
        # Some engines explicitly reject logs for an unreadable driver. Reject
        # arbitrary command/permission/daemon failures rather than count them as proof.
        if (result.returncode != 0 and not result.stdout.strip()
                and "configured logging driver does not support reading" in result.stderr.lower()):
            return
        raise RuntimeError("synthetic_log_absence_unproven")
    else:
        raise RuntimeError("synthetic_log_driver_invalid")


def run_logging_probe(image_id, driver):
    if driver not in {"none", "json-file"}:
        raise RuntimeError("synthetic_log_driver_invalid")
    name = "synthetic-logging-" + uuid4().hex[:12]
    try:
        args = create_args(name, image_id, "unused")
        args[-2:] = ["/src/tests/support/log_output_probe.py"]
        args[args.index("--log-driver") + 1] = driver
        command(args)
        verify_config(json.loads(command(["docker", "inspect", name]))[0],
                      image_id, expected_log_driver=driver)
        # Detached/no attach: marker output never passes through the CI logger.
        command(["docker", "start", name])
        if command(["docker", "wait", name], timeout=10) != "0":
            raise RuntimeError("synthetic_log_emitter_failed")
        data = json.loads(command(["docker", "inspect", name]))[0]
        verify_config(data, image_id, expected_log_driver=driver)
        logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True, timeout=10)
        verify_log_evidence(driver, data["LogPath"], logs)
    finally:
        command(["docker", "rm", "--force", name])
        if command(["docker", "ps", "--all", "--quiet", "--filter", "name=^/" + name + "$"]):
            raise RuntimeError("synthetic_logging_cleanup_failed")
    print("synthetic_logging_ok:" + driver, flush=True)
