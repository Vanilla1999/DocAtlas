"""Host-only opt-in JSON formatting experiment; never changes DTO values."""
from __future__ import annotations

import json
import os
from typing import Any


def serialize_context_json(payload: dict[str, Any]) -> str:
    """Share exact text between whole-DTO budget trials and MCP text delivery.

    Default separators remain unchanged. The experimental host switch applies
    only to docs_context, not patch projections or arbitrary transport payloads.
    """
    from .section_compression import FORMAT, LEGACY_FORMAT

    if (payload.get("context_format") in (LEGACY_FORMAT, FORMAT)
            or (payload.get("kind") == "docs_context"
                and os.environ.get("DOCATLAS_EXPERIMENT_COMPACT_CONTEXT_JSON") == "1")):
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(payload, ensure_ascii=False)
