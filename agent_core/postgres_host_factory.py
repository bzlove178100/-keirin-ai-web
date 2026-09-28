"""Unbound password-only host connection boundary. No driver or secret is configured."""
from pathlib import Path
import os
import pwd
import re
import math
import time

from .durable_secret_store import DurableSecretBackendUnavailable
from .postgres_host_profile import PostgresHostProfile
from .bootstrap_lease import validate_lease
from .host_trust import snapshot_trust

_LIMITS = re.compile(
    r"-c statement_timeout=([1-9][0-9]{0,4}) -c lock_timeout=([1-9][0-9]{0,4}) "
    r"-c idle_in_transaction_session_timeout=([1-9][0-9]{0,4})\Z"
)
_PREFLIGHT = """
SELECT session_user::text, current_user::text, pg_catalog.current_database(),
       pg_catalog.pg_is_in_recovery(), pg_catalog.current_setting('transaction_read_only'),
       (SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_catalog.pg_backend_pid()),
       (SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR NOT rolcanlogin
          FROM pg_catalog.pg_roles WHERE rolname=session_user),
       EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members
               WHERE member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=session_user)),
       (SELECT setting::bigint FROM pg_catalog.pg_settings WHERE name='statement_timeout'),
       (SELECT setting::bigint FROM pg_catalog.pg_settings WHERE name='lock_timeout'),
       (SELECT setting::bigint FROM pg_catalog.pg_settings WHERE name='idle_in_transaction_session_timeout'),
       pg_catalog.current_setting('log_statement'),
       pg_catalog.current_setting('log_parameter_max_length_on_error')::bigint,
       pg_catalog.current_setting('log_duration'),
       pg_catalog.current_setting('log_min_duration_statement')::bigint,
       pg_catalog.current_setting('log_min_duration_sample')::bigint,
       pg_catalog.current_setting('auto_explain.log_min_duration', true),
       pg_catalog.current_setting('auto_explain.log_parameter_max_length', true),
       pg_catalog.current_setting('pgaudit.log_parameter', true)
"""


def _extension_log_policy_safe(auto_duration, auto_parameter_length, pgaudit_parameter):
    # Missing custom GUCs mean the extension is not active in this session. If
    # auto_explain is active, either plan logging must be disabled or Bind values
    # must be suppressed. If pgAudit is active, parameter logging must stay off.
    if auto_duration is None and auto_parameter_length is None:
        auto_safe = True
    elif type(auto_duration) is str and type(auto_parameter_length) is str:
        try:
            duration = int(auto_duration)
            parameter_length = int(auto_parameter_length)
        except ValueError:
            return False
        auto_safe = duration == -1 or parameter_length == 0
    else:
        auto_safe = False
    pgaudit_safe = pgaudit_parameter is None or pgaudit_parameter == "off"
    return auto_safe and pgaudit_safe


def _assert_clean_environment():
    # Reject rather than edit the parent/child environment or silently use a fallback.
    if any(key.startswith("PG") or key in {
        "OPENSSL_CONF", "OPENSSL_MODULES", "SSL_CERT_FILE", "SSL_CERT_DIR",
    } for key in os.environ):
        raise ValueError("ambient_configuration_rejected")
    # Check both Python's home selection and libpq's OS-account home on POSIX.
    homes = {Path.home(), Path(pwd.getpwuid(os.getuid()).pw_dir)}
    for home in homes:
        for relative in (".pgpass", ".pg_service.conf", ".postgresql"):
            if os.path.lexists(home / relative):
                raise ValueError("ambient_configuration_rejected")


class StrictPostgresConnectionFactory:
    """Instantiate inside a trusted top-level process factory, never a task input.

    Constructor is inert. Calls validate adapter limits and reject ambient libpq/TLS
    configuration before reading the injected password source or connecting. A single
    connection is checked before handoff; the source/driver are not retried or logged.
    Use under ProcessDeadlinePostgresSecretBackend to bound source/driver/cleanup hangs.
    Linux/POSIX only. CA ownership, host allowlisting, loader/config integrity, telemetry,
    supervisor limits and actual secret-source custody remain operator review gates.
    """

    def __init__(self, profile, *, driver_connect, password_source, lease_is_current,
                 trusted_ca_sha256, clock=time.time):
        if (type(profile) is not PostgresHostProfile or not callable(driver_connect)
                or not callable(password_source) or not callable(lease_is_current) or not callable(clock)
                or type(trusted_ca_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", trusted_ca_sha256) is None):
            raise ValueError("postgres_host_factory_configuration_invalid")
        self._profile = profile
        self._connect = driver_connect
        self._password_source = password_source
        self._lease_is_current = lease_is_current
        self._trusted_ca_sha256 = trusted_ca_sha256
        self._clock = clock

    def __repr__(self):
        return "StrictPostgresConnectionFactory(<redacted>)"

    def __call__(self, **limits):
        connection = None
        cursor = None
        password = None
        accepted = False
        interrupted = None
        trust = None
        lease = None
        try:
            if set(limits) != {"connect_timeout", "options", "autocommit", "prepare_threshold"}:
                raise ValueError("connection_limits_invalid")
            if (type(limits["connect_timeout"]) is not int or not 2 <= limits["connect_timeout"] <= 30
                    or limits["autocommit"] is not False or limits["prepare_threshold"] is not None
                    or type(limits["options"]) is not str):
                raise ValueError("connection_limits_invalid")
            match = _LIMITS.fullmatch(limits["options"])
            if match is None:
                raise ValueError("connection_limits_invalid")
            statement, lock, idle = map(int, match.groups())
            if not (1 <= lock <= statement <= 30000 and idle == statement):
                raise ValueError("connection_limits_invalid")
            _assert_clean_environment()
            trust = snapshot_trust(self._profile.root_certificate, self._trusted_ca_sha256)
            lease = self._password_source()
            now = self._clock()
            if type(now) not in {int, float} or not math.isfinite(now):
                raise ValueError("bootstrap_clock_invalid")
            anchor = time.monotonic()
            validate_lease(lease, self._profile, now)
            if self._lease_is_current(lease.version) is not True:
                raise ValueError("bootstrap_lease_not_current")
            password = lease.password
            parameters = self._profile.connection_parameters()
            parameters["sslrootcert"] = trust.path
            # Explicit password is required: no .pgpass/client-certificate fallback.
            connection = self._connect(
                **parameters, **limits,
                password=password, passfile=os.devnull, sslcertmode="disable",
                require_auth="scram-sha-256", application_name="agent-secret-host",
            )
            password = None
            if connection.autocommit is not False:
                raise ValueError("transaction_required")
            cursor = connection.cursor()
            cursor.execute(_PREFLIGHT)
            row = cursor.fetchone()
            # The adapter uses parameterized SQL. Reject normal statement/duration
            # logging, error Bind logging, and extension-specific parameter logging
            # before handing the connection to secret-bearing operations.
            expected = (self._profile.login, self._profile.login, self._profile.database,
                        False, "off", True, False, False, statement, lock, idle,
                        "none", 0, "off", -1, -1)
            if (type(row) is not tuple or len(row) != len(expected) + 3
                    or any(type(actual) is not type(wanted) or actual != wanted
                           for actual, wanted in zip(row[:len(expected)], expected))
                    or not _extension_log_policy_safe(*row[len(expected):])
                    or cursor.fetchone() is not None):
                raise ValueError("session_identity_rejected")
            cursor.close()
            cursor = None
            connection.commit()
            after = self._clock()
            if (type(after) not in {int, float} or not math.isfinite(after) or after < now
                    or time.monotonic() - anchor >= lease.expires_at - now):
                raise ValueError("bootstrap_lease_expired")
            validate_lease(lease, self._profile, after)
            if self._lease_is_current(lease.version) is not True:
                raise ValueError("bootstrap_lease_not_current")
            trust.close()
            trust = None
            accepted = True
        except BaseException as error:
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit
        finally:
            password = None
            lease = None
            if trust is not None:
                try:
                    trust.close()
                except BaseException:
                    pass
            if not accepted and connection is not None:
                # Cleanup is still inside the outer child deadline. No raw error leaks.
                try:
                    connection.rollback()
                except BaseException:
                    pass
                for resource in (cursor, connection):
                    if resource is not None:
                        try:
                            resource.close()
                        except BaseException:
                            pass
        if accepted:
            return connection
        if interrupted is not None:
            raise interrupted("postgres_host_factory_interrupted")
        raise DurableSecretBackendUnavailable("postgres_host_factory_unavailable")
