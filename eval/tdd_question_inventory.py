"""Runtime-only inventory and capture checks; not a semantic evaluator."""
from __future__ import annotations


def validate_cases(cases):
    """TDD skeleton: no inventory is accepted until implemented."""
    return []


def load_cases(path, expected_sha256):
    return []


def request_for(case, project_path, lane):
    return {}


def inspect_source(source, project):
    return {"status": "NOT_IMPLEMENTED"}
