from __future__ import annotations

from dataclasses import dataclass
from threading import Barrier, Lock, Thread
from typing import Any, Mapping, Protocol

from agent_core.durable_secret_store import (
    DurableSecretBackend,
    DurableSecretBackendAmbiguousWrite,
    DurableSecretBackendConflict,
)


class DurableBackendConformanceFixture(Protocol):
    """Test-only fixture contract for a concrete durable secret backend.

    The fixture owns an isolated test namespace. ``seed`` is provisioning-only and is not
    part of the runtime backend contract. ``reopen`` must return a new backend client that
    observes the same durable namespace. ``arm_ambiguous_write`` is a fault-injection hook
    used only by conformance tests; it must make the *next* CAS raise
    ``DurableSecretBackendAmbiguousWrite`` either before or after commit as requested.
    """

    def backend(self) -> DurableSecretBackend:
        ...

    def seed(self, key: str, record: Mapping[str, Any]) -> None:
        ...

    def reopen(self) -> DurableSecretBackend:
        ...

    def arm_ambiguous_write(self, *, commits: bool) -> None:
        ...


@dataclass(frozen=True, slots=True)
class DurableBackendConformanceReport:
    initial_read: bool
    cas_commit: bool
    stale_conflict: bool
    restart_persistence: bool
    concurrent_single_winner: bool
    ambiguous_not_committed: bool
    ambiguous_committed: bool

    @property
    def passed(self) -> bool:
        return all(self.to_safe_dict().values())

    def to_safe_dict(self) -> dict[str, bool]:
        return {
            "initial_read": self.initial_read,
            "cas_commit": self.cas_commit,
            "stale_conflict": self.stale_conflict,
            "restart_persistence": self.restart_persistence,
            "concurrent_single_winner": self.concurrent_single_winner,
            "ambiguous_not_committed": self.ambiguous_not_committed,
            "ambiguous_committed": self.ambiguous_committed,
        }


def _record(version: int, marker: str) -> dict[str, Any]:
    # Synthetic marker only. Conformance tests must never use real credential material.
    return {"version": version, "marker": marker}


def run_durable_backend_conformance(
    fixture: DurableBackendConformanceFixture,
    *,
    key: str = "conformance-binding-key",
) -> DurableBackendConformanceReport:
    """Exercise the minimum durable backend semantics without provider/network calls.

    This harness deliberately works at the raw ``DurableSecretBackend`` layer. It proves
    storage/CAS classifications only; it does not prove encryption, access control,
    provider refresh semantics, multi-process/region behavior or production readiness.
    A concrete backend still needs environment-specific security and multi-process tests.
    """

    backend = fixture.backend()
    initial = _record(0, "initial")
    fixture.seed(key, initial)
    initial_read = dict(backend.read(key) or {}) == initial

    v1 = _record(1, "first-commit")
    committed = backend.compare_and_swap(key, expected_version=0, replacement=v1)
    cas_commit = dict(committed) == v1 and dict(backend.read(key) or {}) == v1

    stale_conflict = False
    try:
        backend.compare_and_swap(key, expected_version=0, replacement=_record(1, "stale"))
    except DurableSecretBackendConflict:
        stale_conflict = dict(backend.read(key) or {}) == v1

    restarted = fixture.reopen()
    restart_persistence = dict(restarted.read(key) or {}) == v1

    barrier = Barrier(3)
    outcome_lock = Lock()
    outcomes: list[str] = []

    def contender(marker: str) -> None:
        barrier.wait()
        try:
            value = restarted.compare_and_swap(
                key,
                expected_version=1,
                replacement=_record(2, marker),
            )
            result = "success:" + str(value.get("marker"))
        except DurableSecretBackendConflict:
            result = "conflict"
        with outcome_lock:
            outcomes.append(result)

    threads = [Thread(target=contender, args=("concurrent-a",)), Thread(target=contender, args=("concurrent-b",))]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)
    concurrent_single_winner = (
        len(outcomes) == 2
        and sum(value.startswith("success:") for value in outcomes) == 1
        and outcomes.count("conflict") == 1
        and (restarted.read(key) or {}).get("version") == 2
    )

    current = dict(restarted.read(key) or {})
    fixture.arm_ambiguous_write(commits=False)
    ambiguous_not_committed = False
    try:
        restarted.compare_and_swap(
            key,
            expected_version=2,
            replacement=_record(3, "ambiguous-before-commit"),
        )
    except DurableSecretBackendAmbiguousWrite:
        after = fixture.reopen()
        ambiguous_not_committed = dict(after.read(key) or {}) == current

    fixture.arm_ambiguous_write(commits=True)
    ambiguous_committed = False
    try:
        restarted.compare_and_swap(
            key,
            expected_version=2,
            replacement=_record(3, "ambiguous-after-commit"),
        )
    except DurableSecretBackendAmbiguousWrite:
        after = fixture.reopen()
        ambiguous_committed = dict(after.read(key) or {}) == _record(3, "ambiguous-after-commit")

    return DurableBackendConformanceReport(
        initial_read=initial_read,
        cas_commit=cas_commit,
        stale_conflict=stale_conflict,
        restart_persistence=restart_persistence,
        concurrent_single_winner=concurrent_single_winner,
        ambiguous_not_committed=ambiguous_not_committed,
        ambiguous_committed=ambiguous_committed,
    )
