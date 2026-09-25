from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

EdgeRequester = Callable[[str, dict[str, str], bytes, float], Mapping[str, Any]]
_FUNCTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class HostedTransportError(RuntimeError):
    """Transport/configuration failure before a hosted client can validate response."""


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
        parsed = urlparse(project_url.strip())
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("https_project_url_required")
        if parsed.path not in ("", "/"):
            raise ValueError("project_url_must_not_include_path")
        if not publishable_key.strip():
            raise ValueError("publishable_key_required")
        if not bearer_token.strip():
            raise ValueError("bearer_token_required")
        if not _FUNCTION_RE.fullmatch(function_slug):
            raise ValueError("invalid_function_slug")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
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
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:2000]
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": raw or f"HTTP {exc.code}"}
            if not isinstance(payload, Mapping):
                payload = {"error": f"HTTP {exc.code}"}
            return {
                "success": False,
                **dict(payload),
                "backend_status": exc.code,
            }
        except (URLError, TimeoutError, OSError) as exc:
            raise HostedTransportError(f"edge_transport_failed:{type(exc).__name__}") from exc
        except json.JSONDecodeError as exc:
            raise HostedTransportError("edge_response_invalid_json") from exc

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
        response = self._requester(self.endpoint, headers, body, self.timeout_seconds)
        if not isinstance(response, Mapping):
            raise HostedTransportError("edge_response_object_required")
        return deepcopy(dict(response))
