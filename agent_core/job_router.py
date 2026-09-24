from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

JobType = Literal[
    "research",
    "writing",
    "image_generation",
    "video_generation",
    "coding",
    "keirin_development",
]


@dataclass(frozen=True)
class JobRoute:
    job_type: JobType
    actions: tuple[str, ...]
    description: str


JOB_ROUTES: dict[str, JobRoute] = {
    "research": JobRoute(
        job_type="research",
        actions=("research.web_search", "text.generate"),
        description="Collect public information, then synthesize a grounded textual result.",
    ),
    "writing": JobRoute(
        job_type="writing",
        actions=("text.generate",),
        description="Create or transform text without implying external delivery.",
    ),
    "image_generation": JobRoute(
        job_type="image_generation",
        actions=("image.generate",),
        description="Generate an image artifact; persistence is a separate file capability.",
    ),
    "video_generation": JobRoute(
        job_type="video_generation",
        actions=("video.generate",),
        description="Generate a video artifact; persistence/delivery are separate capabilities.",
    ),
    "coding": JobRoute(
        job_type="coding",
        actions=("code.generate", "code.test"),
        description="Create or modify code in a working context and run verification separately.",
    ),
    "keirin_development": JobRoute(
        job_type="keirin_development",
        actions=("github.read_main", "github.verify_ci"),
        description="Verify current keirin repository state through the existing read-only path.",
    ),
}


@dataclass(frozen=True)
class JobRequest:
    job_id: str
    job_type: JobType
    goal: str
    inputs: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id_required")
        if self.job_type not in JOB_ROUTES:
            raise ValueError(f"unsupported_job_type:{self.job_type}")
        if not self.goal.strip():
            raise ValueError("job_goal_required")


@dataclass(frozen=True)
class JobPlan:
    job_id: str
    job_type: JobType
    goal: str
    actions: tuple[str, ...]
    available_actions: tuple[str, ...]
    missing_actions: tuple[str, ...]
    ready: bool


class JobRouter:
    """Deterministic first-stage router for the broad autonomous-agent scope.

    The router does not call providers and does not grant permissions. It only maps a
    high-level job type to the capability names that an authorized runtime would need.
    Saving, publishing, purchasing, sending or any other side effect remains a separate
    explicit capability and is therefore not silently added to these routes.
    """

    def plan(self, request: JobRequest, *, available_actions: set[str] | frozenset[str]) -> JobPlan:
        request.validate()
        route = JOB_ROUTES[request.job_type]
        available = tuple(action for action in route.actions if action in available_actions)
        missing = tuple(action for action in route.actions if action not in available_actions)
        return JobPlan(
            job_id=request.job_id,
            job_type=request.job_type,
            goal=request.goal,
            actions=route.actions,
            available_actions=available,
            missing_actions=missing,
            ready=not missing,
        )

    def route(self, job_type: str) -> JobRoute:
        route = JOB_ROUTES.get(job_type)
        if route is None:
            raise ValueError(f"unsupported_job_type:{job_type}")
        return route
