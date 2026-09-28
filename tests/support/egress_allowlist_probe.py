"""Client-side proof for an exclusive Docker internal network."""
import errno
import ipaddress
import os
from pathlib import Path
import socket
import time

REQUEST = b"synthetic-egress-check"
RESPONSE = b"synthetic-egress-ok"
PORT = 18443
GATE = Path("/tmp/egress-go")


def wait_for_gate(timeout=10):
    if os.environ.get("SYNTHETIC_EGRESS_GATE") != "1":
        raise RuntimeError("synthetic_egress_gate_required")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if GATE.exists():
            return
        time.sleep(0.02)
    raise RuntimeError("synthetic_egress_gate_timeout")


def require_no_default_route():
    rows = Path("/proc/net/route").read_text().splitlines()[1:]
    for row in rows:
        fields = row.split()
        if len(fields) >= 2 and fields[0] != "lo" and fields[1] == "00000000":
            raise RuntimeError("synthetic_egress_default_route_present")


def require_allowed_ip(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise RuntimeError("synthetic_egress_allowed_ip_invalid") from None
    if address.version != 4 or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise RuntimeError("synthetic_egress_allowed_ip_invalid")
    return str(address)


def connect_allowed(address):
    with socket.create_connection((address, PORT), timeout=2) as connection:
        connection.settimeout(2)
        connection.sendall(REQUEST)
        if connection.recv(64) != RESPONSE:
            raise RuntimeError("synthetic_egress_allowed_response_invalid")


def require_unreachable(address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        try:
            connection.connect((address, 9))
        except OSError as error:
            if error.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
                return
        raise RuntimeError("synthetic_egress_unapproved_not_proven_blocked")


def main():
    # The host observer releases this only after exact live network membership is proven.
    wait_for_gate()
    allowed = require_allowed_ip(os.environ.get("SYNTHETIC_ALLOWED_IP", ""))
    require_no_default_route()
    connect_allowed(allowed)
    # Documentation-only address. No DNS or real endpoint.
    require_unreachable("192.0.2.1")


if __name__ == "__main__":
    main()
