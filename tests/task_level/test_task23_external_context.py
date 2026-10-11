from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from eval.task_level.conditions import CONDITIONS
from eval.task_level.execution import inject_audited_external_context


def _snapshot(task_id: str, content: str) -> dict:
    return {
        "schema_version": "audited-external-context-1",
        "task_id": task_id,
        "library": "example_dependency",
        "version": "1.2.3",
        "source_url": "https://example.test/docs/1.2.3",
        "retrieved_at": "2026-07-13T00:00:00Z",
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "content": content,
    }





