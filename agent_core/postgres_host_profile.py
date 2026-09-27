"""Non-secret, unbound connection policy. Construction performs no I/O."""
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import PurePosixPath
import re

_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]{0,62}\Z")
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_FORBIDDEN_LOGINS = {"postgres", "service_role", "supabase_admin", "authenticator", "anon", "authenticated"}


@dataclass(frozen=True, slots=True, repr=False)
class PostgresHostProfile:
    """Operator-supplied endpoint identity, never task-derived or a credential source.

    The caller must independently approve this host/address/CA and dedicated login.
    This validates shape and fixes transport policy; it cannot certify grants, CA file
    ownership, actual server identity, primary role, ambient configuration or bootstrap
    custody. No runtime factory or activation is included.
    """
    hostname: str
    host_address: str
    port: int
    database: str
    login: str
    root_certificate: str

    def __post_init__(self):
        invalid = False
        try:
            if (type(self.hostname) is not str or len(self.hostname) > 253
                    or "." not in self.hostname
                    or any(not _HOST.fullmatch(label) for label in self.hostname.split("."))):
                raise ValueError()
            if type(self.host_address) is not str or str(ip_address(self.host_address)) != self.host_address:
                raise ValueError()
            if type(self.port) is not int or not 1 <= self.port <= 65535:
                raise ValueError()
            for value in (self.database, self.login):
                if type(value) is not str or not _IDENTIFIER.fullmatch(value):
                    raise ValueError()
            if self.login in _FORBIDDEN_LOGINS:
                raise ValueError()
            cert = self.root_certificate
            if (type(cert) is not str or not cert.startswith("/") or len(cert) > 2048
                    or any(ord(c) < 32 or ord(c) == 127 for c in cert)
                    or ".." in cert.split("/") or str(PurePosixPath(cert)) != cert
                    or cert == "/"):
                raise ValueError()
        except BaseException:
            invalid = True
        if invalid:
            raise ValueError("postgres_host_profile_invalid")

    def __repr__(self):
        return "PostgresHostProfile(<redacted>)"

    def connection_parameters(self):
        # No DSN/service strings, multiple hosts, Unix sockets or TLS downgrade knobs.
        return {
            "host": self.hostname, "hostaddr": self.host_address, "port": self.port,
            "dbname": self.database, "user": self.login,
            "sslmode": "verify-full", "sslrootcert": self.root_certificate,
            "gssencmode": "disable", "ssl_min_protocol_version": "TLSv1.2",
            "target_session_attrs": "read-write",
        }
