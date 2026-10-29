"""CI-only transparent observation of real SQLite FTS statements.

Connections, arguments, queries and results are untouched. The same connection
returned by sqlite3.connect receives SQLite's read-only trace callback. Install
before fixture creation so existing and newly opened connections are observed;
activate only after the separately accounted preparation. No product hook.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import sqlite3
import time


@contextmanager
def observe_sql():
    original = sqlite3.connect
    receipt = {"method": "sqlite_trace_real_connections_v1", "active": False,
               "connections": 0, "attached_connections": 0, "errors": [],
               "statements": []}

    def trace(statement):
        try:
            if not receipt["active"]:
                return
            normalized = " ".join(statement.upper().split())
            if (normalized.startswith("SELECT ")
                    and "FROM RETRIEVAL_CHILDREN_FTS " in normalized
                    and "RETRIEVAL_CHILDREN_FTS MATCH " in normalized):
                receipt["statements"].append({
                    "at_monotonic": time.monotonic(),
                    "sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
                    "statement": statement,
                })
        except Exception as exc:
            receipt["errors"].append("callback: " + type(exc).__name__ + ": " + str(exc))

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)
        receipt["connections"] += 1
        try:
            connection.set_trace_callback(trace)
            receipt["attached_connections"] += 1
        except Exception as exc:
            # Observation must never repair, replace or change product I/O.
            receipt["errors"].append("attach: " + type(exc).__name__ + ": " + str(exc))
        return connection

    sqlite3.connect = connect
    try:
        yield receipt
    finally:
        receipt["active"] = False
        sqlite3.connect = original
