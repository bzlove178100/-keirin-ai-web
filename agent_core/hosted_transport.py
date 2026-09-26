from __future__ import annotations

from copy import deepcopy
import json
import math
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

EdgeRequester = Callable[[str, dict[str, str], bytes, float], Mapping[str, Any]]
_FUNCTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class HostedTransportError(RuntimeError):
    """Transport/configuration failure before a hosted client can validate response."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward owner credentials to a redirect target or replay a POST.
        return None


class SupabaseEdgeTransport:
    """Credential-isolated POST transport for the owner-only agent Edge Function.

    Credentials are constructor-only runtime inputs. They are never added to the JSON
    request body, task state or activity payload. The object repr is intentionally
    redacted. Token refresh/lifecycle belongs to the external host and is not stored by
    this class.
    """

    def __init__(
        self,
        *,
        project_url: str,
        publishable_key: str,
        bearer_token: str,
        function_slug: str = "agent-runtime-dev",
        timeout_seconds: float = 20.0,
        requester: EdgeRequester | None = None,
    ) -> None:
        if not isinstance(project_url, str) or any(ord(c) < 33 for c in project_url):
            raise ValueError("https_project_url_required")
        parsed = urlparse(project_url)
        if parsed.username is not None or parsed.password is not None or not parsed.hostname:
            raise ValueError("project_url_credentials_or_host_invalid")
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("https_project_url_required")
        if parsed.path not in ("", "/"):
            raise ValueError("project_url_must_not_include_path")
        if not publishable_key.strip():
            raise ValueError("publishable_key_required")
        if not bearer_token.strip():
            raise ValueError("bearer_token_required")
        if any(ord(c) < 33 or ord(c) > 126 for c in publishable_key + bearer_token):
            raise ValueError("invalid_credential_header")
        if not _FUNCTION_RE.fullmatch(function_slug):
            raise ValueError("invalid_function_slug")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("positive_timeout_required")

        self._project_url = f"{parsed.scheme}://{parsed.netloc}"
        self._publishable_key = publishable_key
        self._bearer_token = bearer_token
        self.function_slug = function_slug
        self.timeout_seconds = float(timeout_seconds)
        self._requester = requester or self._default_requester

    @property
    def endpoint(self) -> str:
        return f"{self._project_url}/functions/v1/{self.function_slug}"

    def __repr__(self) -> str:
        return (
            f"SupabaseEdgeTransport(project_url={self._project_url!r}, "
            f"function_slug={self.function_slug!r}, credentials='<redacted>')"
        )

    @staticmethod
    def _default_requester(
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with build_opener(_RejectRedirects()).open(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read(2000).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": f"HTTP {exc.code}"}
            if not isinstance(payload, Mapping):
                payload = {"error": f"HTTP {exc.code}"}
            return {
                **dict(payload),
                "success": False,
                "backend_status": exc.code,
            }
        except (URLError, TimeoutError, OSError) as exc:
            raise HostedTransportError(f"edge_transport_failed:{type(exc).__name__}") from None
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HostedTransportError("edge_response_invalid_json") from None

        if not isinstance(payload, Mapping):
            raise HostedTransportError("edge_response_object_required")
        return dict(payload)

    def __call__(self, mode: str, payload: dict[str, Any]) -> Mapping[str, Any]:
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError("hosted_mode_required")
        if not isinstance(payload, dict):
            raise ValueError("hosted_payload_must_be_object")

        detached = deepcopy(payload)
        if "mode" in detached:
            raise ValueError("payload_must_not_override_mode")
        body = json.dumps(
            {"mode": mode.strip(), **detached},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {self._bearer_token}",
            "User-Agent": "keirin-ai-hosted-agent/1",
        }
        # Detect accidental reuse of runtime credentials in payload values or keys.
        if self._contains_credentials({"mode": mode, **detached}):
            raise ValueError("credentials_forbidden_in_payload")
        try:
            response = self._requester(self.endpoint, headers, body, self.timeout_seconds)
        except Exception:
            # An injected requester/network exception can include headers or tokens.
            # No automatic retry: a failed POST may already have persisted state.
            raise HostedTransportError("edge_transport_failed") from None
        if not isinstance(response, Mapping):
            raise HostedTransportError("edge_response_object_required")
        if self._contains_credentials(response):
            raise HostedTransportError("credentials_forbidden_in_response")
        return deepcopy(dict(response))

    def _contains_credentials(self, value: Any) -> bool:
        if isinstance(value, str):
            return self._publishable_key in value or self._bearer_token in value
        if isinstance(value, Mapping):
            return any(self._contains_credentials(k) or self._contains_credentials(v)
                       for k, v in value.items())
        if isinstance(value, (list, tuple)):
            return any(self._contains_credentials(v) for v in value)
        return False
