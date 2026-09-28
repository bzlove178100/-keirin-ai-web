"""Reject false network/log evidence without contacting an external endpoint."""
import errno
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support.network_isolation_probe import require_loopback_only, require_blocked, loopback_control
from host_logging_contract import verify_log_evidence
from support.log_output_probe import STDOUT_MARKER, STDERR_MARKER
from run_host_limits_contract import verify_config
from test_host_limits_fixture import configuration, IMAGE_ID


def result(stdout="", stderr="", code=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)


class NetworkLoggingTests(unittest.TestCase):
    def test_reject_external_interface_or_route_before_network_probes(self):
        require_loopback_only({"lo"}, [], ["0000 lo"])
        for interfaces, ipv4, ipv6 in (({"lo", "eth0"}, [], []),
                                      ({"lo"}, ["eth0 00000000"], []),
                                      ({"lo"}, [], ["0000 eth0"]), (set(), [], [])):
            with self.assertRaises(RuntimeError):
                require_loopback_only(interfaces, ipv4, ipv6)

    def test_timeouts_refusals_and_success_do_not_prove_blocking(self):
        def fail(number):
            def operation():
                raise OSError(number, "SYNTHETIC_ONLY")
            return operation

        for number in (errno.ENETUNREACH, errno.EHOSTUNREACH):
            require_blocked(fail(number))
        for operation in (lambda: None, fail(errno.ECONNREFUSED), fail(errno.ETIMEDOUT), fail(errno.EACCES)):
            with self.assertRaisesRegex(RuntimeError, "synthetic_network_not_proven_blocked"):
                require_blocked(operation)

    def test_loopback_positive_control(self):
        loopback_control()

    def test_logging_positive_control_needs_both_markers_and_log_path(self):
        good = result(STDOUT_MARKER + "\n", STDERR_MARKER + "\n")
        verify_log_evidence("json-file", "/synthetic-json.log", good)
        for path, response in (("", good), ("/synthetic-json.log", result()),
                               ("/synthetic-json.log", result(STDOUT_MARKER)),
                               ("/synthetic-json.log", result(STDOUT_MARKER, STDERR_MARKER, 1))):
            with self.assertRaisesRegex(RuntimeError, "synthetic_log_positive_control_failed"):
                verify_log_evidence("json-file", path, response)

    def test_none_driver_cannot_hide_markers_or_arbitrary_command_errors(self):
        verify_log_evidence("none", "", result())
        verify_log_evidence("none", "", result(stderr="configured logging driver does not support reading", code=1))
        for path, response in (("/unexpected.log", result()), ("", result(STDOUT_MARKER)),
                               ("", result(stderr=STDERR_MARKER)),
                               ("", result(stderr="permission denied", code=1)),
                               ("", result(stderr="daemon unavailable", code=1))):
            with self.assertRaises(RuntimeError):
                verify_log_evidence("none", path, response)

    def test_logging_positive_control_is_explicit_not_a_default_relaxation(self):
        data = configuration()
        data["HostConfig"]["LogConfig"]["Type"] = "json-file"
        with self.assertRaisesRegex(RuntimeError, "synthetic_host_config_mismatch"):
            verify_config(data, IMAGE_ID)
        verify_config(data, IMAGE_ID, expected_log_driver="json-file")
        with self.assertRaisesRegex(RuntimeError, "synthetic_host_log_driver_invalid"):
            verify_config(data, IMAGE_ID, expected_log_driver="journald")


if __name__ == "__main__":
    unittest.main()
