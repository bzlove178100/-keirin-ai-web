"""No DNS or real endpoint: require loopback-only topology before numeric probes."""
import errno
from pathlib import Path
import socket


def require_loopback_only(interfaces, ipv4_routes, ipv6_routes):
    if interfaces != {"lo"}:
        raise RuntimeError("synthetic_network_interfaces_invalid")
    if any(not line.split() or line.split()[0] != "lo" for line in ipv4_routes):
        raise RuntimeError("synthetic_network_ipv4_route_present")
    if any(not line.split() or line.split()[-1] != "lo" for line in ipv6_routes):
        raise RuntimeError("synthetic_network_ipv6_route_present")


def require_blocked(operation):
    try:
        operation()
    except OSError as error:
        # Timeouts/refused connections do not prove network isolation.
        if error.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            return
    raise RuntimeError("synthetic_network_not_proven_blocked")


def loopback_control():
    with socket.socket() as server, socket.socket() as client:
        server.settimeout(1)
        client.settimeout(1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        client.connect(server.getsockname())
        peer, _ = server.accept()
        with peer:
            peer.settimeout(1)
            client.sendall(b"synthetic")
            if peer.recv(16) != b"synthetic":
                raise RuntimeError("synthetic_network_control_failed")


def network_probe():
    require_loopback_only({name for _, name in socket.if_nameindex()},
                          Path("/proc/net/route").read_text().splitlines()[1:],
                          Path("/proc/net/ipv6_route").read_text().splitlines())
    loopback_control()
    # Documentation-only numeric destinations; no hostname resolution. Topology
    # rejection happens first, before any attempt could enter an external route.
    for family, address in ((socket.AF_INET, "192.0.2.1"),
                            (socket.AF_INET6, "2001:db8::1")):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                connection = socket.socket(family, kind)
            except OSError as error:
                if family == socket.AF_INET6 and error.errno == errno.EAFNOSUPPORT:
                    continue  # Disabled IPv6 cannot provide an egress path.
                raise
            with connection:
                connection.settimeout(0.5)
                if kind == socket.SOCK_STREAM:
                    require_blocked(lambda: connection.connect((address, 9)))
                else:
                    require_blocked(lambda: connection.sendto(b"synthetic", (address, 9)))
