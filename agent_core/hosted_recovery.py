from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .hosted_activity import HostedActivityClient, HostedActivityEvent
from .hosted_queue import HostedQueueClient, HostedQueueIntegrityError, HostedQueueLease
from .model import TaskSpec


class HostedRecoveryIntegrityError(RuntimeError):
    """Raised when durable recovery evidence contradicts checkpoint/fence identity."""


@dataclass(frozen=True)
class HostedRecoveryReport:
    task_id: str
    checkpoint_status: str
    revision: int
    attempt_count: int
    max_attempts: int
    lease_generation: int
    lease_owner: str | None
    lease_expires_at: str | None
    lease_expired: bool | None
    observation_events: int
    verification_events: int
    latest_observation_event_id: int | None
    latest_verification_event_id: int | None
    verified: bool | None
    classification: str
    may_reconcile_expired_to_blocked: bool
    reexecution_allowed: bool


class HostedRecoveryInspector:
    """Read-only checkpoint/fence/evidence inspection after interruption.

    Inspection never claims, saves, reconciles, requeues or executes a task. It only
    reads the durable checkpoint row and append-only activity ledger, then classifies
    what is known. In particular, evidence is not treated as proof that a later queue
    transition was acknowledged, and a completed checkpoint is never a retry signal.
    """

    def __init__(
        self,
        *,
        queue: HostedQueueClient,
        activity: HostedActivityClient,
        utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.queue = queue
        self.activity = activity
        self.utcnow = utcnow

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HostedRecoveryIntegrityError("invalid_lease_expiry") from exc
        if parsed.tzinfo is None:
            raise HostedRecoveryIntegrityError("lease_expiry_must_be_timezone_aware")
        return parsed.astimezone(timezone.utc)

    def _all_events(self, task_id: str) -> tuple[HostedActivityEvent, ...]:
        events: list[HostedActivityEvent] = []
        cursor: int | None = None
        while True:
            batch = self.activity.list(task_id=task_id, after_event_id=cursor, limit=200)
            events.extend(batch)
            if len(batch) < 200:
                break
            next_cursor = batch[-1].event_id
            if cursor is not None and next_cursor <= cursor:
                raise HostedRecoveryIntegrityError("activity_cursor_did_not_advance")
            cursor = next_cursor
        return tuple(events)

    @staticmethod
    def _current_generation_evidence(
        lease: HostedQueueLease,
        events: tuple[HostedActivityEvent, ...],
    ) -> tuple[list[HostedActivityEvent], list[HostedActivityEvent]]:
        fingerprint = lease.spec.fingerprint()
        observations: list[HostedActivityEvent] = []
        verifications: list[HostedActivityEvent] = []

        for event in events:
            if event.event_type not in {"github_observation", "github_verification"}:
                continue
            payload = event.payload
            event_fingerprint = payload.get("spec_fingerprint")
            generation = payload.get("lease_generation")
            revision = payload.get("revision")
            evidence = payload.get("evidence")

            if event_fingerprint != fingerprint:
                raise HostedRecoveryIntegrityError("evidence_spec_fingerprint_mismatch")
            if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
                raise HostedRecoveryIntegrityError("invalid_evidence_lease_generation")
            if generation > lease.lease_generation:
                raise HostedRecoveryIntegrityError("evidence_from_future_lease_generation")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise HostedRecoveryIntegrityError("invalid_evidence_revision")
            if revision > lease.revision:
                raise HostedRecoveryIntegrityError("evidence_revision_ahead_of_checkpoint")
            if not isinstance(evidence, dict):
                raise HostedRecoveryIntegrityError("evidence_payload_object_required")
            if generation != lease.lease_generation:
                continue

            if event.event_type == "github_observation":
                observations.append(event)
            else:
                verified = evidence.get("verified")
                if not isinstance(verified, bool):
                    raise HostedRecoveryIntegrityError("verification_evidence_missing_boolean_result")
                verifications.append(event)

        return observations, verifications

    def inspect(self, spec: TaskSpec) -> HostedRecoveryReport:
        spec = TaskSpec.from_dict(spec.to_dict())
        spec.validate()
        try:
            lease = self.queue.inspect(spec)
        except HostedQueueIntegrityError as exc:
            raise HostedRecoveryIntegrityError(str(exc)) from exc

        events = self._all_events(spec.task_id)
        observations, verifications = self._current_generation_evidence(lease, events)
        latest_observation = observations[-1] if observations else None
        latest_verification = verifications[-1] if verifications else None
        verified = None
        if latest_verification is not None:
            verified = bool(latest_verification.payload["evidence"]["verified"])

        lease_expired: bool | None = None
        if lease.status == "running":
            if lease.lease_expires_at is None:
                raise HostedRecoveryIntegrityError("running_checkpoint_missing_lease_expiry")
            now = self.utcnow()
            if now.tzinfo is None:
                raise HostedRecoveryIntegrityError("recovery_clock_must_be_timezone_aware")
            lease_expired = self._parse_timestamp(lease.lease_expires_at) <= now.astimezone(timezone.utc)

        if lease.status == "queued":
            classification = "queued_unstarted" if lease.attempt_count == 0 else "queued_with_prior_attempt_requires_review"
            may_reconcile = False
            reexecution_allowed = lease.attempt_count == 0 and not observations and not verifications
        elif lease.status == "running" and lease_expired is False:
            classification = "running_active_do_not_touch"
            may_reconcile = False
            reexecution_allowed = False
        elif lease.status == "running":
            may_reconcile = True
            reexecution_allowed = False
            if verified is True:
                classification = "running_expired_with_verified_evidence"
            elif verifications:
                classification = "running_expired_with_negative_verification"
            elif observations:
                classification = "running_expired_with_observation_only"
            else:
                classification = "running_expired_without_provider_evidence"
        elif lease.status == "completed":
            may_reconcile = False
            reexecution_allowed = False
            if verified is True:
                classification = "completed_verified_no_reexecution"
            elif verifications:
                classification = "completed_with_negative_verification_integrity_review"
            else:
                classification = "completed_without_verification_evidence_review"
        elif lease.status == "blocked":
            classification = "blocked_requires_explicit_reconciliation"
            may_reconcile = False
            reexecution_allowed = False
        elif lease.status == "failed":
            classification = "failed_requires_explicit_reconciliation"
            may_reconcile = False
            reexecution_allowed = False
        else:  # defensive: HostedQueueClient currently rejects all other states.
            raise HostedRecoveryIntegrityError("unsupported_checkpoint_status")

        return HostedRecoveryReport(
            task_id=lease.task_id,
            checkpoint_status=lease.status,
            revision=lease.revision,
            attempt_count=lease.attempt_count,
            max_attempts=lease.max_attempts,
            lease_generation=lease.lease_generation,
            lease_owner=lease.lease_owner,
            lease_expires_at=lease.lease_expires_at,
            lease_expired=lease_expired,
            observation_events=len(observations),
            verification_events=len(verifications),
            latest_observation_event_id=latest_observation.event_id if latest_observation else None,
            latest_verification_event_id=latest_verification.event_id if latest_verification else None,
            verified=verified,
            classification=classification,
            may_reconcile_expired_to_blocked=may_reconcile,
            reexecution_allowed=reexecution_allowed,
        )
