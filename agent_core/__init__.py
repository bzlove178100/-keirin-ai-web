"""Dependency-light autonomous-agent foundation.

This package intentionally contains no network clients or credentials. Concrete tool
adapters are registered by the caller so permissions and side effects remain explicit.
"""

from .model import (
    ActionResult,
    ArtifactState,
    ArtifactUpdate,
    StepSpec,
    TaskSpec,
    TaskState,
)
from .runner import AgentRunner, BlockedAction, RunOutcome
from .store import FileStateStore

__all__ = [
    "ActionResult",
    "AgentRunner",
    "ArtifactState",
    "ArtifactUpdate",
    "BlockedAction",
    "FileStateStore",
    "RunOutcome",
    "StepSpec",
    "TaskSpec",
    "TaskState",
]
