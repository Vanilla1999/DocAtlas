"""Host-only query tracing; read configuration once, never change retrieval."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import os
import sys
from time import perf_counter
from uuid import uuid4


_enabled = ContextVar("docatlas_query_trace", default=os.environ.get("DOCATLAS_TRACE") == "1")
_request: ContextVar[dict[str, str] | None] = ContextVar("docatlas_trace_request", default=None)


def query_trace_enabled() -> bool:
    return _enabled.get()


@contextmanager
def query_trace(enabled: bool):
    """Explicit private diagnostic runner scope; restore the host setting."""
    token = _enabled.set(enabled)
    try:
        yield
    finally:
        _enabled.reset(token)


def current_request_id() -> str | None:
    request = _request.get()
    return request["request_id"] if request is not None else None


def record_request_status(status: object) -> None:
    """Observe an existing result status without publishing its raw value."""
    request = _request.get()
    if request is not None and isinstance(status, str) and status in ("error", "failed"):
        request["status"] = "error"


def _emit_request_event(event: dict) -> bool:
    try:
        sys.stderr.write(json.dumps(event, separators=(",", ":")) + "\n")
        return True
    except Exception:
        return False


@contextmanager
def request_trace(interface: str, operation: str):
    """Fail-open lifecycle scope; callers supply only fixed interface/operation labels."""
    if not query_trace_enabled():
        yield
        return
    token = None
    try:
        # Success means boundary completion, not sufficient documentation evidence.
        request = {"request_id": uuid4().hex, "status": "success"}
        started = perf_counter()
        token = _request.set(request)
        fields = {
            "request_id": request["request_id"],
            "interface": interface, "operation": operation,
        }
        start_written = _emit_request_event({
            "event": "docatlas_request_start", **fields, "status": "started",
        })
    except Exception:
        if token is not None:
            _request.reset(token)
        _emit_request_event({"event": "docatlas_trace_gap", "status": "unavailable"})
        yield
        return
    try:
        yield
    except BaseException as exc:
        if not isinstance(exc, SystemExit) or exc.code not in (None, 0):
            request["status"] = "error"
        raise
    finally:
        try:
            end_written = _emit_request_event({
                "event": "docatlas_request_end", **fields,
                "status": request["status"],
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "trace_incomplete": not start_written,
            })
            if not end_written:
                _emit_request_event({"event": "docatlas_trace_gap", **fields})
        except Exception:
            _emit_request_event({"event": "docatlas_trace_gap", **fields})
        finally:
            _request.reset(token)


def traced_request(interface: str, operation: str):
    """Wrap a synchronous public boundary, including early returns and exits."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not query_trace_enabled():
                return function(*args, **kwargs)
            with request_trace(interface, operation):
                result = function(*args, **kwargs)
                if isinstance(result, dict):
                    record_request_status(result.get("status"))
                return result
        return wrapped
    return decorate
