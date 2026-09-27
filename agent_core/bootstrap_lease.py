"""Host-only bootstrap lease data; no real secret source is implemented."""
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, repr=False)
class BootstrapPasswordLease:
    login: str
    database: str
    version: int
    expires_at: int
    password: str = field(repr=False)

    def __repr__(self):
        return "BootstrapPasswordLease(<redacted>)"


def validate_lease(lease, profile, now):
    if (type(lease) is not BootstrapPasswordLease
            or type(lease.login) is not str or lease.login != profile.login
            or type(lease.database) is not str or lease.database != profile.database
            or type(lease.version) is not int or not 0 <= lease.version < 2**63
            or type(lease.expires_at) is not int or lease.expires_at <= now
            or type(lease.password) is not str or not lease.password or len(lease.password) > 16384
            or "\x00" in lease.password):
        raise ValueError("bootstrap_lease_invalid")
