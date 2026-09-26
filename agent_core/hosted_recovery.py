from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .hosted_activity import HostedActivityClient, HostedActivityEvent
from .hosted_queue import HostedQueueClient, HostedQueueIntegrityError, HostedQueueLease
from .model import TaskSpec, TaskState


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


@dataclass(frozen=True)
class HostedRecoveryProposal:
    """Non-mutating recovery recommendation bound to one durable snapshot.

    A proposal is evidence for a later authorized decision. It never performs the
    proposed action and never authorizes execution/retry by itself.
    """

    task_id: str
    classification: str
    proposed_action: str
    expected_revision: int | None
    lease_generation: int | None
    reason: str
    automatic_execution_allowed: bool
    blocked_state: dict | None = None


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

    def _inspect_snapshot(self, spec: TaskSpec) -> tuple[HostedQueueLease, HostedRecoveryReport]:
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

        report = HostedRecoveryReport(
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
        return lease, report

    def inspect(self, spec: TaskSpec) -> HostedRecoveryReport:
        _, report = self._inspect_snapshot(spec)
        return report

    @staticmethod
    def _snapshot_identity(lease: HostedQueueLease, report: HostedRecoveryReport) -> tuple:
        return (
            lease.task_id,
            lease.status,
            lease.revision,
            lease.attempt_count,
            lease.max_attempts,
            lease.lease_generation,
            lease.lease_owner,
            lease.lease_expires_at,
            report.classification,
            report.observation_events,
            report.verification_events,
            report.latest_observation_event_id,
            report.latest_verification_event_id,
            report.verified,
        )

    def propose(self, spec: TaskSpec) -> HostedRecoveryProposal:
        """Return a non-mutating next-action proposal after a stable double read.

        The second read catches durable state/evidence changes between inspection and
        proposal construction. A future authorized reconciler must still use revision
        CAS + lease generation fencing; this proposal alone is never sufficient to
        execute a mutation or provider action.
        """
        first_lease, first_report = self._inspect_snapshot(spec)
        second_lease, second_report = self._inspect_snapshot(spec)
        if self._snapshot_identity(first_lease, first_report) != self._snapshot_identity(second_lease, second_report):
            raise HostedRecoveryIntegrityError("recovery_snapshot_changed")

        report = second_report
        lease = second_lease
        common = {
            "task_id": report.task_id,
            "classification": report.classification,
            "automatic_execution_allowed": False,
        }

        if report.may_reconcile_expired_to_blocked:
            blocked = TaskState.from_dict(deepcopy(lease.state.to_dict()))
            blocked.status = "blocked"
            blocked.blocked_reason = "expired_lease_requires_reconciliation"
            blocked.last_error = blocked.last_error or "hosted_run_interrupted_or_expired"
            blocked.touch()
            return HostedRecoveryProposal(
                **common,
                proposed_action="reconcile_expired_to_blocked",
                expected_revision=lease.revision,
                lease_generation=lease.lease_generation,
                reason="expired running lease must be converted to blocked before any later decision",
                blocked_state=blocked.to_dict(),
            )

        if report.classification == "queued_unstarted":
            return HostedRecoveryProposal(
                **common,
                proposed_action="eligible_for_first_execution",
                expected_revision=lease.revision,
                lease_generation=lease.lease_generation,
                reason="no prior attempt or provider evidence was observed; separate execution authorization is still required",
            )
        if report.classification == "running_active_do_not_touch":
            return HostedRecoveryProposal(
                **common,
                proposed_action="do_not_touch",
                expected_revision=lease.revision,
                lease_generation=lease.lease_generation,
                reason="active lease is still owned; do not reconcile or replay",
            )
        if report.checkpoint_status == "completed":
            return HostedRecoveryProposal(
                **common,
                proposed_action="no_reexecution",
                expected_revision=lease.revision,
                lease_generation=lease.lease_generation,
                reason="completed checkpoint is not a retry signal regardless of evidence completeness",
            )
        if report.checkpoint_status in {"blocked", "failed"} or report.classification == "queued_with_prior_attempt_requires_review":
            return HostedRecoveryProposal(
                **common,
                proposed_action="manual_reconciliation_required",
                expected_revision=lease.revision,
                lease_generation=lease.lease_generation,
                reason="durable prior-attempt state requires an explicit reconciliation decision",
            )

        return HostedRecoveryProposal(
            **common,
            proposed_action="manual_review",
            expected_revision=lease.revision,
            lease_generation=lease.lease_generation,
            reason="no automatic recovery action is permitted for this durable state",
        )
