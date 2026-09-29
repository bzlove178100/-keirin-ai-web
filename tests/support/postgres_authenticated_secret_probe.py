"""Stdlib PostgreSQL TLS/SCRAM probe for synthetic secret read/CAS composition."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import struct
import time

SSL_REQUEST_CODE = 80877103
PROTOCOL_VERSION = 196608
GATE = Path("/tmp/auth-go")
PASSWORD_FILE = Path("/tmp/bootstrap-password")


class PgError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError("synthetic_auth_probe_config_missing")
    return value


def _pack_message(kind, payload):
    return kind + struct.pack("!I", len(payload) + 4) + payload


def _read_exact(stream, length):
    chunks = bytearray()
    while len(chunks) < length:
        chunk = stream.recv(length - len(chunks))
        if not chunk:
            raise RuntimeError("synthetic_auth_probe_protocol_eof")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_message(stream):
    kind = _read_exact(stream, 1)
    length = struct.unpack("!I", _read_exact(stream, 4))[0]
    if length < 4 or length > 1024 * 1024:
        raise RuntimeError("synthetic_auth_probe_protocol_length")
    return kind, _read_exact(stream, length - 4)


def _error_fields(payload):
    fields = {}
    offset = 0
    while offset < len(payload) and payload[offset] != 0:
        key = chr(payload[offset])
        offset += 1
        end = payload.find(b"\x00", offset)
        if end < 0:
            raise RuntimeError("synthetic_auth_probe_error_frame")
        fields[key] = payload[offset:end].decode("utf-8", "replace")
        offset = end + 1
    return fields


def _raise_server_error(payload):
    fields = _error_fields(payload)
    raise PgError(fields.get("C", "XXXXX"), fields.get("M", "synthetic_postgres_error"))


def _scram_escape(value):
    return value.replace("=", "=3D").replace(",", "=2C")


def _xor(left, right):
    return bytes(a ^ b for a, b in zip(left, right))


def _parse_scram(value):
    parts = {}
    for item in value.split(","):
        if len(item) < 3 or item[1] != "=":
            raise RuntimeError("synthetic_auth_probe_scram_frame")
        key = item[0]
        if key in parts:
            raise RuntimeError("synthetic_auth_probe_scram_duplicate")
        parts[key] = item[2:]
    return parts


def _password_message(payload):
    return _pack_message(b"p", payload)


def _authenticate(stream, user, password):
    nonce = base64.b64encode(secrets.token_bytes(18)).decode("ascii").rstrip("=")
    client_first_bare = f"n={_scram_escape(user)},r={nonce}"
    gs2_header = "n,,"
    expected_server_signature = None
    state = "start"

    while True:
        kind, payload = _read_message(stream)
        if kind == b"E":
            _raise_server_error(payload)
        if kind == b"R":
            if len(payload) < 4:
                raise RuntimeError("synthetic_auth_probe_auth_frame")
            auth_type = struct.unpack("!I", payload[:4])[0]
            body = payload[4:]
            if auth_type == 10 and state == "start":
                mechanisms = [item.decode() for item in body.split(b"\x00") if item]
                if "SCRAM-SHA-256" not in mechanisms:
                    raise RuntimeError("synthetic_auth_probe_scram_required")
                first = (gs2_header + client_first_bare).encode()
                initial = b"SCRAM-SHA-256\x00" + struct.pack("!I", len(first)) + first
                stream.sendall(_password_message(initial))
                state = "first-sent"
                continue
            if auth_type == 11 and state == "first-sent":
                server_first = body.decode("utf-8")
                fields = _parse_scram(server_first)
                server_nonce = fields.get("r", "")
                if not server_nonce.startswith(nonce) or server_nonce == nonce:
                    raise RuntimeError("synthetic_auth_probe_scram_nonce")
                try:
                    salt = base64.b64decode(fields["s"], validate=True)
                    iterations = int(fields["i"])
                except (KeyError, ValueError):
                    raise RuntimeError("synthetic_auth_probe_scram_parameters") from None
                if not 4096 <= iterations <= 1000000 or not salt:
                    raise RuntimeError("synthetic_auth_probe_scram_parameters")
                salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
                client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
                stored_key = hashlib.sha256(client_key).digest()
                client_final_without_proof = (
                    "c=" + base64.b64encode(gs2_header.encode()).decode("ascii") + ",r=" + server_nonce
                )
                auth_message = client_first_bare + "," + server_first + "," + client_final_without_proof
                client_signature = hmac.new(stored_key, auth_message.encode(), hashlib.sha256).digest()
                proof = base64.b64encode(_xor(client_key, client_signature)).decode("ascii")
                server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
                expected_server_signature = base64.b64encode(
                    hmac.new(server_key, auth_message.encode(), hashlib.sha256).digest()
                ).decode("ascii")
                stream.sendall(_password_message((client_final_without_proof + ",p=" + proof).encode()))
                state = "final-sent"
                continue
            if auth_type == 12 and state == "final-sent":
                final = _parse_scram(body.decode("utf-8"))
                if final.get("v") != expected_server_signature:
                    raise RuntimeError("synthetic_auth_probe_scram_server_signature")
                state = "server-verified"
                continue
            if auth_type == 0 and state == "server-verified":
                state = "authenticated"
                continue
            raise RuntimeError("synthetic_auth_probe_auth_unexpected")
        if kind in {b"S", b"K", b"N"}:
            continue
        if kind == b"Z":
            if state != "authenticated" or payload != b"I":
                raise RuntimeError("synthetic_auth_probe_not_ready")
            return
        raise RuntimeError("synthetic_auth_probe_startup_unexpected")


def _startup(stream, user, database, password):
    params = {
        "user": user,
        "database": database,
        "application_name": "agent-secret-host-composed",
        "options": "-c statement_timeout=5000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000",
    }
    body = struct.pack("!I", PROTOCOL_VERSION)
    for key, value in params.items():
        body += key.encode() + b"\x00" + value.encode() + b"\x00"
    body += b"\x00"
    stream.sendall(struct.pack("!I", len(body) + 4) + body)
    _authenticate(stream, user, password)


def _query(stream, sql, params=()):
    parse = b"\x00" + sql.encode() + b"\x00" + struct.pack("!H", 0)
    bind = bytearray(b"\x00\x00")
    bind.extend(struct.pack("!H", 0))
    bind.extend(struct.pack("!H", len(params)))
    for value in params:
        if value is None:
            bind.extend(struct.pack("!i", -1))
        else:
            encoded = str(value).encode()
            bind.extend(struct.pack("!i", len(encoded)))
            bind.extend(encoded)
    bind.extend(struct.pack("!H", 0))
    describe = b"P\x00"
    execute = b"\x00" + struct.pack("!I", 0)
    stream.sendall(
        _pack_message(b"P", parse)
        + _pack_message(b"B", bytes(bind))
        + _pack_message(b"D", describe)
        + _pack_message(b"E", execute)
        + _pack_message(b"S", b"")
    )

    columns = None
    rows = []
    pending_error = None
    while True:
        kind, payload = _read_message(stream)
        if kind == b"E":
            fields = _error_fields(payload)
            pending_error = PgError(fields.get("C", "XXXXX"), fields.get("M", "synthetic_postgres_error"))
            continue
        if kind == b"T":
            count = struct.unpack("!H", payload[:2])[0]
            offset = 2
            names = []
            for _ in range(count):
                end = payload.find(b"\x00", offset)
                if end < 0 or end + 19 > len(payload):
                    raise RuntimeError("synthetic_auth_probe_row_description")
                names.append(payload[offset:end].decode())
                offset = end + 1 + 18
            columns = names
            continue
        if kind == b"D":
            count = struct.unpack("!H", payload[:2])[0]
            offset = 2
            values = []
            for _ in range(count):
                if offset + 4 > len(payload):
                    raise RuntimeError("synthetic_auth_probe_data_row")
                length = struct.unpack("!i", payload[offset:offset + 4])[0]
                offset += 4
                if length == -1:
                    values.append(None)
                else:
                    if length < 0 or offset + length > len(payload):
                        raise RuntimeError("synthetic_auth_probe_data_row")
                    values.append(payload[offset:offset + length].decode())
                    offset += length
            rows.append(values)
            continue
        if kind in {b"1", b"2", b"n", b"C", b"N"}:
            continue
        if kind == b"Z":
            if pending_error is not None:
                raise pending_error
            return columns or [], rows
        raise RuntimeError("synthetic_auth_probe_query_unexpected")


def _single(stream, sql, params=()):
    _, rows = _query(stream, sql, params)
    if len(rows) != 1 or len(rows[0]) != 1:
        raise RuntimeError("synthetic_auth_probe_single_result")
    return rows[0][0]


def _expect_error(code, message, action):
    try:
        action()
    except PgError as error:
        if error.code != code or error.message != message:
            raise RuntimeError("synthetic_auth_probe_error_contract") from None
        return
    raise RuntimeError("synthetic_auth_probe_expected_error_missing")


def _wait_for_release():
    deadline = time.monotonic() + 10
    while not GATE.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("synthetic_auth_probe_gate_timeout")
        time.sleep(0.02)
    if not PASSWORD_FILE.is_file():
        raise RuntimeError("synthetic_auth_probe_password_missing")


def main():
    if os.environ.get("SYNTHETIC_POSTGRES_AUTH_SECRET_PROBE") != "1":
        raise RuntimeError("synthetic_auth_probe_gate_required")

    address = _required("SYNTHETIC_DB_IP")
    port = int(_required("SYNTHETIC_DB_PORT"))
    hostname = _required("SYNTHETIC_DB_HOST")
    ca = Path(_required("SYNTHETIC_DB_CA"))
    user = _required("SYNTHETIC_DB_USER")
    database = _required("SYNTHETIC_DB_NAME")
    if user != "secret_test_host_a" or database != "agent_checkpoint_ci" or not ca.is_file():
        raise RuntimeError("synthetic_auth_probe_identity_invalid")

    _wait_for_release()
    password = PASSWORD_FILE.read_text()
    PASSWORD_FILE.unlink()
    if password != "SYNTHETIC:tls-ci-only":
        raise RuntimeError("synthetic_auth_probe_password_invalid")

    raw = socket.create_connection((address, port), timeout=3)
    secure = None
    try:
        raw.settimeout(5)
        raw.sendall(struct.pack("!II", 8, SSL_REQUEST_CODE))
        if raw.recv(1) != b"S":
            raise RuntimeError("synthetic_auth_probe_ssl_rejected")
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        secure = context.wrap_socket(raw, server_hostname=hostname)
        raw = None
        secure.settimeout(5)
        if not secure.getpeercert() or not secure.cipher():
            raise RuntimeError("synthetic_auth_probe_peer_unverified")

        _startup(secure, user, database, password)
        preflight = _single(
            secure,
            "SELECT jsonb_build_object("
            "'session_user',session_user,'current_user',current_user,'database',current_database(),"
            "'recovery',pg_is_in_recovery(),'read_only',current_setting('transaction_read_only'),"
            "'ssl',(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()))::text",
        )
        observed = json.loads(preflight)
        if observed != {
            "session_user": user,
            "current_user": user,
            "database": database,
            "recovery": False,
            "read_only": "off",
            "ssl": True,
        }:
            raise RuntimeError("synthetic_auth_probe_preflight_invalid")

        initial = json.loads(_single(
            secure,
            "SELECT agent_credential_private.read_binding($1::text)::text",
            ("binding-a",),
        ))
        if (initial.get("version") != 0 or initial.get("state") != "ready"
                or initial.get("provider_id") != "provider-a"
                or initial.get("account_id") != "account-a"
                or initial.get("capabilities") != ["read:one", "write:one"]
                or initial.get("refresh_secret") != "SYNTHETIC:a0"):
            raise RuntimeError("synthetic_auth_probe_initial_record_invalid")

        _expect_error(
            "42501", "credential_binding_denied",
            lambda: _single(secure, "SELECT agent_credential_private.read_binding($1::text)::text", ("binding-b",)),
        )

        replacement = dict(initial)
        replacement["version"] = 1
        replacement["refresh_secret"] = "SYNTHETIC:composed-a1"
        replacement_json = json.dumps(replacement, separators=(",", ":"), sort_keys=True)
        updated = json.loads(_single(
            secure,
            "SELECT agent_credential_private.cas_binding($1::text,$2::bigint,$3::jsonb)::text",
            ("binding-a", "0", replacement_json),
        ))
        if updated != replacement:
            raise RuntimeError("synthetic_auth_probe_cas_result_invalid")
        reread = json.loads(_single(
            secure,
            "SELECT agent_credential_private.read_binding($1::text)::text",
            ("binding-a",),
        ))
        if reread != replacement:
            raise RuntimeError("synthetic_auth_probe_readback_invalid")

        _expect_error(
            "P0002", "credential_version_conflict",
            lambda: _single(
                secure,
                "SELECT agent_credential_private.cas_binding($1::text,$2::bigint,$3::jsonb)::text",
                ("binding-a", "0", replacement_json),
            ),
        )
        untouched = json.loads(_single(
            secure,
            "SELECT agent_credential_private.read_binding($1::text)::text",
            ("binding-a",),
        ))
        if untouched != replacement:
            raise RuntimeError("synthetic_auth_probe_stale_cas_mutated")

        secure.sendall(_pack_message(b"X", b""))
        secure.close()
        secure = None
    finally:
        if secure is not None:
            secure.close()
        if raw is not None:
            raw.close()
        try:
            PASSWORD_FILE.unlink()
        except FileNotFoundError:
            pass

    print("synthetic_postgres_authenticated_secret_probe_ok", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(24) from None
