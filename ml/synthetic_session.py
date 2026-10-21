"""Bounded, local-only generated-session checkpoints; real-data training stays off."""
from __future__ import annotations

import hashlib
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
LEGACY_BACKUP_FILENAME = 'synthetic-session-v1-before-migration.json'
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

    def _read(self, filename=None, *, sync=False):
        try:
            fd = os.open(self.filename if filename is None else filename,
                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.directory_fd)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError('session_file_invalid')
            data = handle.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('session_too_large')
            if sync:
                os.fsync(handle.fileno())
            return data

    def inspect_legacy_backup(self):
        """Read only: correlate a bounded v1 original with the last saved session.

        Return bytes only for a valid, related original. The raw-byte digest
        binds a subsequent download to this observation, not to provenance.
        """
        try:
            if self._read() != self.expected:
                return {'status': 'current_changed'}, None
            raw = self._read(LEGACY_BACKUP_FILENAME)
            if raw is None:
                return {'status': 'missing'}, None
            envelope = json.loads(raw)
            if (not isinstance(envelope, dict) or set(envelope) != {'payload', 'sha256'} or
                    envelope['sha256'] != _digest(envelope['payload'])):
                raise ValueError('backup_envelope_invalid')
            old = envelope['payload']
            validate_session(old)
            if old['schema_version'] != LEGACY_SCHEMA:
                raise ValueError('backup_v1_required')
            current = json.loads(self.expected)['payload'] if self.expected else None
            if current is None:
                related = False
            elif current['schema_version'] == LEGACY_SCHEMA:
                related = raw == self.expected
            else:
                legacy = {'series': old['series'], 'scheduled': old['scheduled'],
                          'snapshot_hashes': {key: s['snapshot_sha256'] for key, s in old['snapshots'].items()}}
                related = (current['legacy'] == legacy and
                           all(_canonical(current['snapshots'].get(key)) == _canonical(value)
                               for key, value in old['snapshots'].items()) and
                           all(_canonical(current['histories'].get(key)) == _canonical(value)
                               for key, value in old['histories'].items()))
            if not related:
                return {'status': 'unrelated'}, None
            return {'status': 'available', 'sha256': hashlib.sha256(raw).hexdigest(),
                    'bytes': len(raw), 'snapshots': len(old['snapshots']),
                    'histories': len(old['histories'])}, raw
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            return {'status': 'invalid'}, None

    def _preserve_legacy(self, payload):
        if (self.filename != FILENAME or payload.get('schema_version') != SCHEMA or
                self.expected is None or
                json.loads(self.expected)['payload']['schema_version'] != LEGACY_SCHEMA):
            return
        temporary = 'session-v1-backup-' + uuid4().hex + '.partial'
        created = False
        try:
            previous = self._read(LEGACY_BACKUP_FILENAME, sync=True)
            if previous is not None:
                if previous != self.expected:
                    raise ValueError('migration_backup_already_contains_different_record')
                # A prior process may have completed the file but not the
                # directory sync. Confirm both before replacing the v1 source.
            else:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.directory_fd)
                created = True
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(self.expected)  # Preserve exact original bytes, not a reserialization.
                    handle.flush()
                    os.fsync(handle.fileno())
                # Exclusive publication: never replace an existing backup,
                # even if it appears after the earlier read.
                os.link(temporary, LEGACY_BACKUP_FILENAME,
                        src_dir_fd=self.directory_fd, dst_dir_fd=self.directory_fd,
                        follow_symlinks=False)
                os.unlink(temporary, dir_fd=self.directory_fd)
                created = False
            os.fsync(self.directory_fd)
            if self._read(LEGACY_BACKUP_FILENAME) != self.expected:
                raise ValueError('migration_backup_verification_failed')
        except (OSError, ValueError) as exc:
            self.failed = True
            raise SessionSaveError('session_migration_backup_failed_restart_required') from exc
        finally:
            if created:
                try:
                    os.unlink(temporary, dir_fd=self.directory_fd)
                except OSError:
                    pass

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
            self._preserve_legacy(payload)
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
