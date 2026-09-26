from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import HostedRecoveryInspector  # noqa: E402
from tools.prepare_hosted_recovery import prepare_hosted_recovery  # noqa: E402


class PrepareHostedRecoveryTest(unittest.TestCase):
    def test_factory_constructs_without_network_io(self):
        calls = []

        def requester(*args):
            calls.append(args)
            raise AssertionError("factory must not perform network I/O")

        inspector = prepare_hosted_recovery(
            project_url="https://example.supabase.co",
            publishable_key="publishable-fixture-value",
            owner_bearer_token="owner-fixture-value",
            requester=requester,
        )
        self.assertIsInstance(inspector, HostedRecoveryInspector)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
