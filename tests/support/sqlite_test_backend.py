"""Synthetic-only SQLite backend for offline, multi-process CAS tests.

Never use this module for real credentials: it has no encryption or access control.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from agent_core.durable_secret_store import (
    DurableSecretBackendAmbiguousWrite,
    DurableSecretBackendConflict,
    DurableSecretBackendUnavailable,
)


class SQLiteTestBackend:
    def __init__(self, path: Path, fault: dict[str, str] | None = None) -> None:
        self.path = path
        self.fault = fault

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def seed(self, key: str, record: Mapping[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS records (binding_key TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO records (binding_key, version, payload) VALUES (?, ?, ?)",
                (key, record["version"], json.dumps(dict(record), sort_keys=True)),
            )

    def read(self, key: str) -> Mapping[str, Any] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT payload FROM records WHERE binding_key = ?", (key,)
                ).fetchone()
            return None if row is None else json.loads(row[0])
        except sqlite3.Error:
            raise DurableSecretBackendUnavailable("test_backend_unavailable") from None

    def compare_and_swap(
        self, key: str, *, expected_version: int, replacement: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        if replacement.get("version") != expected_version + 1:
            raise ValueError("test_replacement_version_invalid")
        connection = None
        commit_started = False
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE records SET version = ?, payload = ? WHERE binding_key = ? AND version = ?",
                (replacement["version"], json.dumps(dict(replacement), sort_keys=True), key, expected_version),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise DurableSecretBackendConflict("test_backend_conflict")
            mode = None if self.fault is None else self.fault.pop("mode", None)
            if mode == "before":
                connection.rollback()
                raise DurableSecretBackendAmbiguousWrite("test_backend_ambiguous")
            commit_started = True
            connection.commit()
            if mode == "after":
                raise DurableSecretBackendAmbiguousWrite("test_backend_ambiguous")
            return dict(replacement)
        except sqlite3.Error:
            classification = (
                DurableSecretBackendAmbiguousWrite if commit_started else DurableSecretBackendUnavailable
            )
            raise classification("test_backend_storage_failure") from None
        finally:
            if connection is not None:
                connection.close()
