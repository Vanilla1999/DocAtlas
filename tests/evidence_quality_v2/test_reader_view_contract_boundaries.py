"""Contract boundaries for eval-only serialization, independent of reader scores."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from eval.evidence_quality_v2.reader_views import (
    UnsupportedReaderView, parse_reader_view_text, reader_view, render_reader_view,
)


def _packet():
    return {
        "kind": "docs_context", "status": "ok",
        "answer_supported": False, "answer_available": False, "edit_ready": False,
        "sources": [{"evidence_id": "ev-boundary", "path": "docs/rule.md",
                     "snippet": "Keep the caller's resource open.\n"}],
    }







