"""Bounded, local-only synthetic workbench checkpoints; never a training source."""
from __future__ import annotations

import json
from datetime import timedelta, timezone
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from ml.model_history import _canonical, _digest, _validate_history, validate_snapshot
from ml.settle_snapshot import _iso

LEGACY_SCHEMA = 'synthetic-workbench-session-v1'
SCHEMA = 'synthetic-workbench-session-v2'
JST = timezone(timedelta(hours=9))
FILENAME = 'synthetic-session.json'
MAX_BYTES = 32 * 1024 * 1024
MAX_SNAPSHOTS = 20


def validate_session(value):
    fields = {'schema_version', 'synthetic_only', 'scheduled',
              'snapshots', 'histories', 'current'}
    version = value.get('schema_version') if isinstance(value, dict) else None
    fields.add('series' if version == LEGACY_SCHEMA else 'legacy')
    if (not isinstance(value, dict) or set(value) != fields or
            version not in (LEGACY_SCHEMA, SCHEMA) or value['synthetic_only'] is not True):
        raise ValueError('session_schema_invalid')
    scheduled = _iso(value['scheduled'], 'session_scheduled')
    snapshots, histories = value['snapshots'], value['histories']
    if (not isinstance(snapshots, dict) or not isinstance(histories, dict) or
            len(snapshots) > MAX_SNAPSHOTS or not set(histories).issubset(snapshots)):
        raise ValueError('session_records_invalid')
    current = value['current']
    if (snapshots and (not isinstance(current, str) or current not in snapshots)) or (not snapshots and current is not None):
        raise ValueError('session_current_invalid')
    legacy = value if version == LEGACY_SCHEMA else value['legacy']
    legacy_hashes = {}
    if legacy is not None:
        if version == SCHEMA:
            if (not isinstance(legacy, dict) or set(legacy) != {'series', 'scheduled', 'snapshot_hashes'} or
                    not isinstance(legacy['snapshot_hashes'], dict) or
                    not set(legacy['snapshot_hashes']).issubset(snapshots)):
                raise ValueError('session_legacy_invalid')
            legacy_hashes = legacy['snapshot_hashes']
        series = legacy['series']
        if type(series) is not int or not 0 <= series <= 1000000:
            raise ValueError('session_series_invalid')
        legacy_scheduled = _iso(legacy['scheduled'], 'session_scheduled')
    # v2 assigns one synthetic schedule per JST day. Legacy records keep their
    # original validation rules, and are never renumbered or re-dated.
    schedules = {scheduled.astimezone(JST).date(): scheduled}
    new_days, legacy_days = [], []
    for key, snapshot in snapshots.items():
        if not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key):
            raise ValueError('session_snapshot_key_invalid')
        validate_snapshot(snapshot, synthetic=True)
        race = snapshot['prediction']['race']
        count = snapshot['prediction']['input_quality']['rider_count']
        number = race['race_number']
        start = _iso(snapshot['scheduled_start'], 'scheduled_start')
        if race['venue'] != 'SYNTHETIC':
            raise ValueError('generated_session_race_required')
        if version == LEGACY_SCHEMA or key in legacy_hashes:
            if version == SCHEMA and legacy_hashes[key] != snapshot['snapshot_sha256']:
                raise ValueError('session_legacy_snapshot_mismatch')
            if (number-count) % 10 or not 0 <= (number-count)//10 <= series:
                raise ValueError('generated_session_race_required')
            if (number-count)//10 == series and start != legacy_scheduled:
                raise ValueError('session_schedule_mismatch')
            legacy_days.append(start.astimezone(JST).date())
        else:
            if number != count:
                raise ValueError('generated_session_race_required')
            day = start.astimezone(JST).date()
            if start > scheduled or schedules.setdefault(day, start) != start:
                raise ValueError('session_schedule_mismatch')
            new_days.append(day)
        if key in histories:
            _validate_history(histories[key])
            if _canonical(histories[key]['snapshot']) != _canonical(snapshot):
                raise ValueError('session_history_snapshot_mismatch')
    if version == SCHEMA and legacy is not None:
        boundary = max([legacy_scheduled.astimezone(JST).date(), *legacy_days])
        if min([scheduled.astimezone(JST).date(), *new_days]) <= boundary:
            raise ValueError('session_legacy_schedule_overlap')


class SessionSaveError(RuntimeError):
    pass


class SessionStore:
    """One local POSIX process, fixed filenames, atomic replace and explicit fsync.

    Locks are cooperative; hashes detect accidental changes, not provenance.
    Filesystems/hosts are not thereby qualified for production durability.
    """
    filename = FILENAME
    lock_filename = 'session.lock'
    temporary_prefix = 'session-'
    validate = staticmethod(validate_session)

    def __init__(self, directory: Path):
        import fcntl
        self.directory_fd = self.lock_fd = None
        self.failed = False
        self.expected = None
        self.loaded = None
        try:
            directory = Path(directory)
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.lock_fd = os.open(self.lock_filename, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                   0o600, dir_fd=self.directory_fd)
            if not stat.S_ISREG(os.fstat(self.lock_fd).st_mode) or os.fstat(self.lock_fd).st_nlink != 1:
                raise ValueError('session_lock_not_regular')
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError('session_already_open') from exc
            self.expected = self._read()
            if self.expected is not None:
                envelope = json.loads(self.expected)
                if not isinstance(envelope, dict) or set(envelope) != {'payload', 'sha256'}:
                    raise ValueError('session_envelope_invalid')
                if envelope['sha256'] != _digest(envelope['payload']):
                    raise ValueError('session_digest_mismatch')
                self.validate(envelope['payload'])
                self.loaded = envelope['payload']
        except BaseException:
            self.close()
            raise

    def close(self):
        for name in ('lock_fd', 'directory_fd'):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)

    def _read(self):
        try:
            fd = os.open(self.filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.directory_fd)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError('session_file_invalid')
            data = handle.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('session_too_large')
            return data

    def save(self, payload):
        if self.failed:
            raise SessionSaveError('session_restart_required')
        self.validate(payload)
        data = (_canonical({'payload': payload, 'sha256': _digest(payload)}) + '\n').encode('utf-8')
        if len(data) > MAX_BYTES:
            raise ValueError('session_too_large')
        temporary = self.temporary_prefix + uuid4().hex + '.partial'
        replaced = False
        created = False
        try:
            if self._read() != self.expected:
                raise ValueError('session_changed_outside_workbench')
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=self.directory_fd)
            created = True
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.filename, src_dir_fd=self.directory_fd, dst_dir_fd=self.directory_fd)
            replaced = True
            os.fsync(self.directory_fd)
            self.expected = data
        except (OSError, ValueError) as exc:
            self.failed = True
            code = 'session_save_uncertain_restart_required' if replaced else 'session_save_failed_restart_required'
            raise SessionSaveError(code) from exc
        finally:
            if created:
                try:
                    os.unlink(temporary, dir_fd=self.directory_fd)
                except FileNotFoundError:
                    pass
