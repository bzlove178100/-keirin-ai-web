"""Build two provenance-pinned CI clients; never install a system package/unit."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

FIX = "8f5eaeb143dd9e58503980ae5f63dd78c463180e"
UBUNTU = "https://archive.ubuntu.com/ubuntu/pool/main/s/systemd/"
SOURCES = {
    "systemd_255.4.orig.tar.gz": (UBUNTU + "systemd_255.4.orig.tar.gz", "96e75bd08c57ad401677456fb88ef54a9f05bb1695693013bc6ecce839640fd5"),
    "systemd_255.4-1ubuntu8.17.debian.tar.xz": (UBUNTU + "systemd_255.4-1ubuntu8.17.debian.tar.xz", "4695ff34f83b1f7e6e02bf3cfac2e2a44ac76b6cfc5a38c0081bac6919d547bb"),
    "systemd_255.4-1ubuntu8.17.dsc": (UBUNTU + "systemd_255.4-1ubuntu8.17.dsc", "8e5f4e5a7b7ee457214be1efd1ea1d380186c38b146d8c98af5da0f625d3c396"),
    "fix.patch": ("https://github.com/systemd/systemd/commit/" + FIX + ".patch", "b581a4c784a89648f8a8f25866a2b66ad57e54e6644a3ab2c8b6fe75fef86ffb"),
}
CONFIG = ["--prefix=/usr", "--sysconfdir=/etc", "--libdir=lib", "--libexecdir=lib",
          "--buildtype=release", "-Dmode=release", "-Dauto_features=disabled",
          "-Dnetworkd=true", "-Dlink-networkd-shared=false", "-Dtests=false",
          "-Dinstall-tests=false", "-Dtranslations=false", "-Dresolve=false",
          "-Dversion-tag=255.4-kc-dhcp6-ci"]
DEPOT = Path("/tmp/kc-dhcp6-ci-client")
POSTPROCESS = ["patchelf", "--remove-rpath"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_input(path, expected):
    if not path.is_file() or path.stat().st_size > 20_000_000 or digest(path) != expected:
        raise RuntimeError("PINNED_CLIENT_INPUT_MISMATCH")


def run(*args, cwd=None, timeout=600):
    subprocess.run(args, cwd=cwd, check=True, timeout=timeout)


def build():
    # No caller-supplied source, patch, executable, install prefix or output path.
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("KC_DHCP6_BUILD_CI") != "1" or os.geteuid() == 0):
        raise RuntimeError("UNPRIVILEGED_CI_BUILD_REQUIRED")
    base = Path(os.environ["RUNNER_TEMP"])
    if not base.is_absolute() or not base.is_dir():
        raise RuntimeError("RUNNER_TEMP_REQUIRED")
    output = base / "kc-dhcp6-client-output"
    output.mkdir(mode=0o755)  # Refuse stale output instead of silently reusing it.
    with tempfile.TemporaryDirectory(prefix="kc-dhcp6-source-", dir=base) as temp:
        root = Path(temp)
        for name, (url, expected) in SOURCES.items():
            target = root / name
            run("curl", "--proto", "=https", "--tlsv1.2", "-fsSL", "--max-time", "90", url, "-o", str(target), timeout=100)
            checked_input(target, expected)
        # SHA-256 pins are verified above; this is not a claim of PGP validation.
        run("dpkg-source", "--no-check", "-x", str(root / "systemd_255.4-1ubuntu8.17.dsc"), str(root / "source"), cwd=root)
        source, builddir = root / "source", root / "build"
        lease = source / "src/libsystemd-network/sd-dhcp6-lease.c"
        old = lease.read_bytes()
        broken = b"DEFINE_GET_TIME_FUNCTIONS(t2, lifetime_t1);"
        corrected = b"DEFINE_GET_TIME_FUNCTIONS(t2, lifetime_t2);"
        if old.count(broken) != 1 or corrected in old:
            raise RuntimeError("EXPECTED_ORIGINAL_GETTER_REQUIRED")
        run("meson", "setup", str(builddir), str(source), *CONFIG)
        hashes = {}
        for variant in ("original", "patched"):
            if variant == "patched":
                run("patch", "--batch", "--fuzz=0", "-p1", "-i", str(root / "fix.patch"), cwd=source)
                if lease.read_bytes() != old.replace(broken, corrected):
                    raise RuntimeError("EXACT_UPSTREAM_ONE_LINE_FIX_REQUIRED")
            run("ninja", "-C", str(builddir), "-j2", "systemd-networkd")
            binary = builddir / "systemd-networkd"
            # Meson's common executable template reserves install_rpath even
            # for internal-static builds. Remove it identically in both clients.
            run(*POSTPROCESS, str(binary), timeout=10)
            dynamic = subprocess.run(["readelf", "-d", str(binary)], check=True, capture_output=True, timeout=10).stdout
            print("CI_CLIENT_DYNAMIC", variant, [line.decode() for line in dynamic.splitlines() if any(key in line for key in (b"NEEDED", b"RPATH", b"RUNPATH"))], flush=True)
            if any(value in dynamic for value in (b"libsystemd-shared", b"RPATH", b"RUNPATH")):
                raise RuntimeError("SELF_CONTAINED_INTERNAL_CLIENT_REQUIRED")
            target = output / ("networkd-" + variant)
            shutil.copyfile(binary, target)
            target.chmod(0o755)
            hashes[variant] = digest(target)
            run(str(target), "--version", timeout=10)
        if hashes["original"] == hashes["patched"]:
            raise RuntimeError("DISTINCT_CLIENT_BUILDS_REQUIRED")
        manifest = {"schema": 1, "source_version": "255.4-1ubuntu8.17",
                    "inputs": {k: v[1] for k, v in SOURCES.items()}, "fix": FIX,
                    "configure": CONFIG, "postprocess": POSTPROCESS, "binaries": hashes,
                    "original_lease_sha256": hashlib.sha256(old).hexdigest(),
                    "patched_lease_sha256": digest(lease)}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print("CI_CLIENT_BUILD_PROVENANCE", json.dumps(manifest), flush=True)


def client_path(variant):
    if variant not in ("original", "patched"):
        raise RuntimeError("FIXED_CI_CLIENT_VARIANT_REQUIRED")
    if os.environ.get("KC_DHCP6_CI") != "1":
        raise RuntimeError("DHCP6_CLIENT_OPT_IN_REQUIRED")
    binary = DEPOT / ("networkd-" + variant)
    manifest_path = DEPOT / "manifest.json"
    for path in (DEPOT, binary, manifest_path):
        info = path.lstat()
        regular = stat.S_ISDIR(info.st_mode) if path == DEPOT else stat.S_ISREG(info.st_mode)
        if not regular or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError("ROOT_OWNED_IMMUTABLE_CLIENT_REQUIRED")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schema") != 1 or manifest.get("source_version") != "255.4-1ubuntu8.17"
            or manifest.get("inputs") != {k: v[1] for k, v in SOURCES.items()}
            or manifest.get("fix") != FIX or manifest.get("configure") != CONFIG
            or manifest.get("postprocess") != POSTPROCESS
            or manifest.get("binaries", {}).get(variant) != digest(binary)):
        raise RuntimeError("CLIENT_BUILD_MANIFEST_MISMATCH")
    print("CI_CLIENT", variant, digest(binary), flush=True)
    return str(binary)


class Tests(unittest.TestCase):
    def test_build_refuses_without_ci_before_output_or_commands(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(Path, "mkdir") as mkdir, patch(__name__ + ".run") as command:
            with self.assertRaisesRegex(RuntimeError, "UNPRIVILEGED_CI_BUILD_REQUIRED"):
                build()
            mkdir.assert_not_called()
            command.assert_not_called()

    def test_altered_download_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input"
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "PINNED_CLIENT_INPUT_MISMATCH"):
                checked_input(path, hashlib.sha256(b"original").hexdigest())

    def test_arbitrary_executable_variant_refused_before_read(self):
        with patch.object(Path, "lstat") as read:
            with self.assertRaisesRegex(RuntimeError, "FIXED_CI_CLIENT_VARIANT_REQUIRED"):
                client_path("../../usr/bin/sh")
            read.assert_not_called()


if __name__ == "__main__":
    if sys.argv[1:] == ["--build"]:
        build()
    else:
        unittest.main(verbosity=2)
