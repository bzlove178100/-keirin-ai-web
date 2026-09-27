"""Unbound password-only host connection boundary. No driver or secret is configured."""
from pathlib import Path
import os
import pwd
import re

from .durable_secret_store import DurableSecretBackendUnavailable
from .postgres_host_profile import PostgresHostProfile

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
       (SELECT setting::bigint FROM pg_catalog.pg_settings WHERE name='idle_in_transaction_session_timeout')
"""


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

    def __init__(self, profile, *, driver_connect, password_source):
        if type(profile) is not PostgresHostProfile or not callable(driver_connect) or not callable(password_source):
            raise ValueError("postgres_host_factory_configuration_invalid")
        self._profile = profile
        self._connect = driver_connect
        self._password_source = password_source

    def __repr__(self):
        return "StrictPostgresConnectionFactory(<redacted>)"

    def __call__(self, **limits):
        connection = None
        cursor = None
        password = None
        accepted = False
        interrupted = None
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
            password = self._password_source()
            if type(password) is not str or not password or len(password) > 16384 or "\x00" in password:
                raise ValueError("bootstrap_password_invalid")
            # Explicit password is required: no .pgpass/client-certificate fallback.
            connection = self._connect(
                **self._profile.connection_parameters(), **limits,
                password=password, passfile=os.devnull, sslcertmode="disable",
                application_name="agent-secret-host",
            )
            password = None
            if connection.autocommit is not False:
                raise ValueError("transaction_required")
            cursor = connection.cursor()
            cursor.execute(_PREFLIGHT)
            row = cursor.fetchone()
            expected = (self._profile.login, self._profile.login, self._profile.database,
                        False, "off", True, False, False, statement, lock, idle)
            if (type(row) is not tuple or len(row) != len(expected)
                    or any(type(actual) is not type(wanted) or actual != wanted
                           for actual, wanted in zip(row, expected))
                    or cursor.fetchone() is not None):
                raise ValueError("session_identity_rejected")
            cursor.close()
            cursor = None
            connection.commit()
            accepted = True
        except BaseException as error:
            if isinstance(error, KeyboardInterrupt):
                interrupted = KeyboardInterrupt
            elif isinstance(error, SystemExit):
                interrupted = SystemExit
        finally:
            password = None
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
