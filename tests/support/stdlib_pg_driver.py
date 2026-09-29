"""Tiny test-only PostgreSQL v3 TLS/SCRAM driver shim.

It implements only the DB-API-like surface exercised by StrictPostgresConnectionFactory
and PostgresSecretBackend. It is not a production driver and intentionally has no
ambient configuration, retry, pooling, telemetry or DSN support.
"""
from types import SimpleNamespace
import json
import os
import re
import socket
import ssl
import struct

from support.postgres_authenticated_secret_probe import (
    SSL_REQUEST_CODE, PROTOCOL_VERSION, _authenticate, _error_fields, _pack_message,
    _read_exact, _read_message,
)

_BOOL_OID = 16
_INT_OIDS = frozenset({20, 21, 23, 26})
_JSON_OIDS = frozenset({114, 3802})
_PLACEHOLDER = re.compile(r"%s")


class DriverError(Exception):
    def __init__(self, sqlstate, message):
        super().__init__(message)
        self.sqlstate = sqlstate
        self.diag = SimpleNamespace(message_primary=message)


def _server_error(payload):
    fields = _error_fields(payload)
    return DriverError(fields.get("C", "XXXXX"), fields.get("M", "synthetic_postgres_error"))


def _rewrite_placeholders(sql, count):
    found = len(_PLACEHOLDER.findall(sql))
    if found != count:
        raise ValueError("synthetic_driver_parameter_count_invalid")
    index = 0

    def replace(_match):
        nonlocal index
        index += 1
        return "$" + str(index)

    return _PLACEHOLDER.sub(replace, sql)


def _decode_value(raw, oid):
    if raw is None:
        return None
    if oid == _BOOL_OID:
        if raw == b"t":
            return True
        if raw == b"f":
            return False
        raise RuntimeError("synthetic_driver_bool_invalid")
    text = raw.decode("utf-8")
    if oid in _INT_OIDS:
        return int(text)
    if oid in _JSON_OIDS:
        return json.loads(text)
    return text


def _row_description(payload):
    if len(payload) < 2:
        raise RuntimeError("synthetic_driver_row_description_invalid")
    count = struct.unpack("!H", payload[:2])[0]
    offset = 2
    oids = []
    for _ in range(count):
        end = payload.find(b"\x00", offset)
        if end < 0 or end + 19 > len(payload):
            raise RuntimeError("synthetic_driver_row_description_invalid")
        field = end + 1
        oid = struct.unpack("!I", payload[field + 6:field + 10])[0]
        oids.append(oid)
        offset = field + 18
    if offset != len(payload):
        raise RuntimeError("synthetic_driver_row_description_invalid")
    return oids


def _data_row(payload, oids):
    if len(payload) < 2:
        raise RuntimeError("synthetic_driver_data_row_invalid")
    count = struct.unpack("!H", payload[:2])[0]
    if count != len(oids):
        raise RuntimeError("synthetic_driver_data_row_invalid")
    offset = 2
    values = []
    for oid in oids:
        if offset + 4 > len(payload):
            raise RuntimeError("synthetic_driver_data_row_invalid")
        length = struct.unpack("!i", payload[offset:offset + 4])[0]
        offset += 4
        if length == -1:
            raw = None
        else:
            if length < 0 or offset + length > len(payload):
                raise RuntimeError("synthetic_driver_data_row_invalid")
            raw = payload[offset:offset + length]
            offset += length
        values.append(_decode_value(raw, oid))
    if offset != len(payload):
        raise RuntimeError("synthetic_driver_data_row_invalid")
    return tuple(values)


def _query(stream, sql, params):
    rewritten = _rewrite_placeholders(sql, len(params))
    parse = b"\x00" + rewritten.encode("utf-8") + b"\x00" + struct.pack("!H", 0)
    bind = bytearray(b"\x00\x00")
    bind.extend(struct.pack("!H", 0))
    bind.extend(struct.pack("!H", len(params)))
    for value in params:
        if value is None:
            bind.extend(struct.pack("!i", -1))
        else:
            encoded = str(value).encode("utf-8")
            bind.extend(struct.pack("!i", len(encoded)))
            bind.extend(encoded)
    bind.extend(struct.pack("!H", 0))
    stream.sendall(
        _pack_message(b"P", parse)
        + _pack_message(b"B", bytes(bind))
        + _pack_message(b"D", b"P\x00")
        + _pack_message(b"E", b"\x00" + struct.pack("!I", 0))
        + _pack_message(b"S", b"")
    )

    oids = None
    rows = []
    pending_error = None
    while True:
        kind, payload = _read_message(stream)
        if kind == b"E":
            pending_error = _server_error(payload)
            continue
        if kind == b"T":
            oids = _row_description(payload)
            continue
        if kind == b"D":
            if oids is None:
                raise RuntimeError("synthetic_driver_data_without_description")
            rows.append(_data_row(payload, oids))
            continue
        if kind in {b"1", b"2", b"n", b"C", b"N", b"S"}:
            continue
        if kind == b"Z":
            if pending_error is not None:
                raise pending_error
            return rows
        raise RuntimeError("synthetic_driver_query_message_invalid")


def _startup(stream, *, user, database, password, application_name, options):
    params = {
        "user": user,
        "database": database,
        "application_name": application_name,
        "options": options,
    }
    body = struct.pack("!I", PROTOCOL_VERSION)
    for key, value in params.items():
        body += key.encode("utf-8") + b"\x00" + value.encode("utf-8") + b"\x00"
    body += b"\x00"
    stream.sendall(struct.pack("!I", len(body) + 4) + body)
    _authenticate(stream, user, password)


class Cursor:
    def __init__(self, connection):
        self._connection = connection
        self._rows = []
        self._index = 0
        self._closed = False

    def execute(self, sql, params=()):
        if self._closed or self._connection._closed:
            raise RuntimeError("synthetic_driver_cursor_closed")
        if type(sql) is not str or not isinstance(params, (tuple, list)):
            raise ValueError("synthetic_driver_query_invalid")
        self._rows = _query(self._connection._stream, sql, tuple(params))
        self._index = 0
        return self

    def fetchone(self):
        if self._closed:
            raise RuntimeError("synthetic_driver_cursor_closed")
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def close(self):
        self._closed = True
        self._rows = []
        self._index = 0


class Connection:
    autocommit = False

    def __init__(self, stream):
        self._stream = stream
        self._closed = False

    def cursor(self):
        if self._closed:
            raise RuntimeError("synthetic_driver_connection_closed")
        return Cursor(self)

    def commit(self):
        if self._closed:
            raise RuntimeError("synthetic_driver_connection_closed")
        _query(self._stream, "COMMIT", ())

    def rollback(self):
        if self._closed:
            raise RuntimeError("synthetic_driver_connection_closed")
        _query(self._stream, "ROLLBACK", ())

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._stream.sendall(_pack_message(b"X", b""))
        except OSError:
            pass
        self._stream.close()


def connect(**kwargs):
    expected = {
        "host", "hostaddr", "port", "dbname", "user", "sslmode", "sslrootcert",
        "gssencmode", "ssl_min_protocol_version", "target_session_attrs",
        "connect_timeout", "options", "autocommit", "prepare_threshold", "password",
        "passfile", "sslcertmode", "require_auth", "application_name",
    }
    if set(kwargs) != expected:
        raise ValueError("synthetic_driver_connect_contract_invalid")
    if (kwargs["sslmode"] != "verify-full" or kwargs["gssencmode"] != "disable"
            or kwargs["ssl_min_protocol_version"] != "TLSv1.2"
            or kwargs["target_session_attrs"] != "read-write"
            or kwargs["autocommit"] is not False or kwargs["prepare_threshold"] is not None
            or kwargs["passfile"] != os.devnull or kwargs["sslcertmode"] != "disable"
            or kwargs["require_auth"] != "scram-sha-256"
            or kwargs["application_name"] != "agent-secret-host"):
        raise ValueError("synthetic_driver_connect_contract_invalid")
    for field in ("host", "hostaddr", "dbname", "user", "sslrootcert", "options", "password"):
        if type(kwargs[field]) is not str or not kwargs[field]:
            raise ValueError("synthetic_driver_connect_contract_invalid")
    if type(kwargs["port"]) is not int or type(kwargs["connect_timeout"]) is not int:
        raise ValueError("synthetic_driver_connect_contract_invalid")

    raw = socket.create_connection(
        (kwargs["hostaddr"], kwargs["port"]), timeout=kwargs["connect_timeout"]
    )
    secure = None
    try:
        raw.settimeout(max(2, kwargs["connect_timeout"]))
        raw.sendall(struct.pack("!II", 8, SSL_REQUEST_CODE))
        if _read_exact(raw, 1) != b"S":
            raise RuntimeError("synthetic_driver_ssl_rejected")
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=kwargs["sslrootcert"])
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        secure = context.wrap_socket(raw, server_hostname=kwargs["host"])
        raw = None
        secure.settimeout(max(2, kwargs["connect_timeout"]))
        if not secure.getpeercert() or not secure.cipher():
            raise RuntimeError("synthetic_driver_peer_unverified")
        _startup(
            secure,
            user=kwargs["user"],
            database=kwargs["dbname"],
            password=kwargs["password"],
            application_name=kwargs["application_name"],
            options=kwargs["options"],
        )
        return Connection(secure)
    except BaseException:
        if secure is not None:
            secure.close()
        if raw is not None:
            raw.close()
        raise
