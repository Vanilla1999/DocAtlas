"""Host-only query tracing; read configuration once, never change retrieval."""
from contextlib import contextmanager
from contextvars import ContextVar
import os


_enabled = ContextVar("docatlas_query_trace", default=os.environ.get("DOCATLAS_TRACE") == "1")


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
