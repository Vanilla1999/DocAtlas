from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from eval.evidence_quality_v2.reader_views import (
    parse_reader_view_text,
    reader_view,
    render_reader_view,
)


def _packet():
    return {
        "status": "ok",
        "kind": "docs_context",
        "context_status": "ready",
        "context_available": True,
        "answer_supported": False,
        "answer_available": False,
        "support_status": "retrieval_only",
        "answer_policy": "cite_only",
        "coverage_policy": "retrieval_attribution_only",
        "query_coverage": "full",
        "retrieval_coverage": "full",
        "facet_coverage": "unverified",
        "covered_query_ids": ["query-original"],
        "missing_query_ids": [],
        "missing_facets": [],
        "facets": [],
        "sources": [
            {
                "evidence_id": "ev-test",
                "path_or_url": "docs/client.md",
                "section": "Client > Waiting",
                "snippet": "`Client.wait(7, connect=31)`\nDo not use this with shared state.",
                "version_binding": "v2",
                "content_sha256": "a" * 64,
                "project_identity": "project:test",
                "authority": "source_of_truth",
                "instruction_trust": "data",
                "scope": "project",
                "line_start": 4,
                "line_end": 5,
            }
        ],
        "context_quality": {"status": "unverified", "reasons": ["coverage_unverified"]},
        "read_next": [],
        "edit_ready": False,
        "investigation_allowed": True,
        "estimated_tokens": 321,
    }















