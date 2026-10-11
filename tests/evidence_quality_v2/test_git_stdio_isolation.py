"""Git inspection must not consume an MCP host's pipe; fixture DBs must close."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from docmancer.docs import impact

ROOT = Path(__file__).resolve().parents[2]


def test_bounded_child_gets_eof_without_consuming_host_stdin() -> None:
    # The outer process owns the host stream. Test the real bounded runner,
    # not a mocked Popen that assumes the required redirection.
    program = """
import json, sys
from docmancer.docs.impact import _run_process_bounded
result = _run_process_bounded(
    [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read(1))'],
    max_stdout_bytes=64, timeout_seconds=5,
)
print(json.dumps({'child': result[0].decode(), 'code': result[2],
                  'timeout': result[4], 'host': sys.stdin.buffer.read().decode()}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program], input=b"MCP-host-only\n", cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=True,
    )
    result = json.loads(completed.stdout)
    assert result["child"] == "", "bounded child consumed the host's MCP stdin"
    assert result["host"] == "MCP-host-only\n"
    assert result["code"] == 0 and result["timeout"] is False


def test_bounded_child_still_preserves_failure_and_stderr() -> None:
    out, err, code, truncated, timed_out = impact._run_process_bounded(
        [sys.executable, "-c", "import sys; print('failed', file=sys.stderr); sys.exit(7)"],
        max_stdout_bytes=64, timeout_seconds=5,
    )
    assert out == b"" and b"failed" in err and code == 7
    assert truncated is False and timed_out is False



