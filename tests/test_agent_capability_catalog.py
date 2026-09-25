from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import capability_by_action, capability_catalog  # noqa: E402


class CapabilityCatalogTest(unittest.TestCase):
    def test_required_broad_agent_domains_are_declared(self):
        contracts = capability_catalog()
        self.assertEqual(
            {contract.domain for contract in contracts},
            {"research", "text", "image", "video", "code", "learning", "reporting"},
        )

    def test_actions_are_unique_and_disabled_by_default(self):
        contracts = capability_catalog()
        actions = [contract.capability.action for contract in contracts]
        self.assertEqual(len(actions), len(set(actions)))
        self.assertTrue(all(contract.default_enabled is False for contract in contracts))

    def test_generation_capabilities_require_explicit_execute_permissions(self):
        for action in ("text.generate", "image.generate", "video.generate", "code.generate"):
            contract = capability_by_action(action)
            self.assertEqual(contract.capability.access, "execute")
            self.assertTrue(contract.requires_external_provider)
            self.assertFalse(contract.default_enabled)
            self.assertTrue(contract.capability.required_permissions)

    def test_research_contract_does_not_enable_keirin_auto_fetch(self):
        research = capability_by_action("research.read_public_sources")
        self.assertEqual(research.capability.access, "read")
        self.assertFalse(research.default_enabled)
        self.assertIn("keirin race-data fetching", research.notes)

    def test_report_generation_is_separate_from_delivery(self):
        report = capability_by_action("report.generate")
        self.assertEqual(report.capability.access, "execute")
        self.assertTrue(report.capability.supports_dry_run)
        self.assertFalse(report.requires_external_provider)


if __name__ == "__main__":
    unittest.main()
