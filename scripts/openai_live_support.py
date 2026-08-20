from __future__ import annotations

from typing import Any

import httpx


_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_NON_RETRYABLE_429_MARKERS = frozenset({
    "insufficient_quota",
    "billing_hard_limit_reached",
    "billing_not_active",
})


def _safe_text(value: Any, *, limit: int = 128) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def safe_openai_http_diagnostic(response: httpx.Response) -> dict[str, Any]:
    """Return only non-secret provider fields that are safe to persist."""
    error: dict[str, Any] = {}
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error = payload["error"]

    return {
        "status": int(response.status_code),
        "error_type": _safe_text(error.get("type")),
        "error_code": _safe_text(error.get("code")),
        "retry_after": _safe_text(response.headers.get("retry-after")),
        "request_id": _safe_text(response.headers.get("x-request-id")),
    }


def should_retry_openai_response(response: httpx.Response) -> bool:
    status = int(response.status_code)
    if status not in _RETRYABLE_STATUS_CODES:
        return False
    if status != 429:
        return True

    diagnostic = safe_openai_http_diagnostic(response)
    markers = {
        str(value).lower()
        for value in (diagnostic.get("error_type"), diagnostic.get("error_code"))
        if value
    }
    return not bool(markers & _NON_RETRYABLE_429_MARKERS)


def retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    """Honor numeric Retry-After but keep local benchmark waits bounded."""
    raw = response.headers.get("retry-after")
    if raw:
        try:
            return min(30.0, max(0.0, float(raw)))
        except ValueError:
            pass
    return min(30.0, 2.0 * (2**attempt))


class OpenAILiveHTTPError(RuntimeError):
    def __init__(self, response: httpx.Response) -> None:
        self.diagnostic = safe_openai_http_diagnostic(response)
        parts = [f"status={self.diagnostic['status']}"]
        for key in ("error_type", "error_code", "retry_after", "request_id"):
            value = self.diagnostic.get(key)
            if value:
                parts.append(f"{key}={value}")
        super().__init__("openai_http_error " + " ".join(parts))
