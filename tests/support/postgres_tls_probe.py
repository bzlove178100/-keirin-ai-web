"""Minimal PostgreSQL TLS handshake probe for the disposable hardened host fixture."""
import os
from pathlib import Path
import socket
import ssl
import struct

SSL_REQUEST_CODE = 80877103


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("synthetic_tls_probe_config_missing")
    return value


def main():
    if os.environ.get("SYNTHETIC_POSTGRES_TLS_PROBE") != "1":
        raise RuntimeError("synthetic_tls_probe_gate_required")

    address = _required("SYNTHETIC_DB_IP")
    port = int(_required("SYNTHETIC_DB_PORT"))
    hostname = _required("SYNTHETIC_DB_HOST")
    ca = Path(_required("SYNTHETIC_DB_CA"))
    if not ca.is_file():
        raise RuntimeError("synthetic_tls_probe_ca_missing")

    raw = socket.create_connection((address, port), timeout=3)
    try:
        raw.settimeout(3)
        raw.sendall(struct.pack("!II", 8, SSL_REQUEST_CODE))
        if raw.recv(1) != b"S":
            raise RuntimeError("synthetic_tls_probe_ssl_rejected")
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        with context.wrap_socket(raw, server_hostname=hostname) as secure:
            if not secure.getpeercert() or not secure.cipher():
                raise RuntimeError("synthetic_tls_probe_peer_unverified")
            raw = None
    finally:
        if raw is not None:
            raw.close()

    print("synthetic_postgres_tls_probe_ok", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(23) from None
