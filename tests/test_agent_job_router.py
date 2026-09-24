from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_core import JOB_ROUTES, JobRequest, JobRouter  # noqa: E402


class AgentJobRouterTest(unittest.TestCase):
    def test_required_broad_job_types_are_present(self):
        self.assertEqual(
            set(JOB_ROUTES),
            {
                "research",
                "writing",
                "image_generation",
                "video_generation",
                "coding",
                "keirin_development",
            },
        )

    def test_research_requires_collection_and_synthesis(self):
        route = JOB_ROUTES["research"]
        self.assertEqual(route.actions, ("research.web_search", "text.generate"))

    def test_generation_routes_do_not_silently_add_publish_or_send(self):
        forbidden_fragments = ("publish", "send", "deliver", "purchase", "delete")
        for job_type in ("writing", "image_generation", "video_generation", "coding"):
            actions = JOB_ROUTES[job_type].actions
            self.assertTrue(actions)
            for action in actions:
                self.assertFalse(any(fragment in action for fragment in forbidden_fragments), (job_type, action))

    def test_router_reports_missing_capabilities_instead_of_faking_readiness(self):
        router = JobRouter()
        request = JobRequest(
            job_id="JOB-IMG-1",
            job_type="image_generation",
            goal="generate a campaign image",
        )
        missing = router.plan(request, available_actions=set())
        self.assertFalse(missing.ready)
        self.assertEqual(missing.missing_actions, ("image.generate",))

        ready = router.plan(request, available_actions={"image.generate"})
        self.assertTrue(ready.ready)
        self.assertEqual(ready.available_actions, ("image.generate",))
        self.assertEqual(ready.missing_actions, ())

    def test_coding_keeps_generation_and_verification_separate(self):
        plan = JobRouter().plan(
            JobRequest(job_id="JOB-CODE-1", job_type="coding", goal="implement and test a change"),
            available_actions={"code.generate", "code.test"},
        )
        self.assertEqual(plan.actions, ("code.generate", "code.test"))
        self.assertTrue(plan.ready)

    def test_keirin_route_uses_existing_read_only_verification_path(self):
        route = JOB_ROUTES["keirin_development"]
        self.assertEqual(route.actions, ("github.read_main", "github.verify_ci"))

    def test_unknown_job_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported_job_type"):
            JobRouter().route("unknown")


if __name__ == "__main__":
    unittest.main()
