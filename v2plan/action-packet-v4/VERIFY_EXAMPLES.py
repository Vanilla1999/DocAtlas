"""Offline reproducible measurements of the integrated patch projection.

Run from the integration root with PYTHONPATH=. using the existing interpreter.
No live retrieval, provider calls, index writes or corpus expansion.
"""
from copy import deepcopy
import hashlib
import json

import jsonschema
import mcp.types as mcp_types

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application.model_visible_projection import (
    project_patch_context, validate_model_visible_projection,
)
from docmancer.mcp._docs_server_part01 import (
    _mcp_tool_result, call_docs_tool_payload, current_docs_surface,
)


def window(index, text):
    return {
        "path": f"docs/component-{index}.md", "source_class": "project_doc",
        "doc_scope": "project", "content": text, "snippet": text,
        "display_text": text, "stable_chunk_id": f"measurement-child-{index}",
        "parent_logical_id": f"measurement-parent-{index}",
        "char_start": 0, "char_end": len(text), "line_start": 1,
        "line_end": text.count("\n") + 1,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "version": "2.0", "retrieval_rank": index + 1,
    }


def examples():
    text = "Delivery records preserve their immutable evidence identity."
    item = window(0, text)
    large_texts = [
        f"Component {i} uses the dedicated delivery partition partition-{i}; "
        f"its immutable audit identity is component-{i}-delivery. "
        f"Acknowledgement sequence {i + 1} records the independent delivery state."
        for i in range(18)
    ]
    return [
        ("empty failure", [], []),
        ("partial evidence", [item], [text, "The independent retry constraint is absent."]),
        ("small complete", [item], [text]),
        ("unique necessary >2000", [window(i, text) for i, text in enumerate(large_texts)], large_texts),
    ]


def measure():
    rows = []
    for name, evidence, requirements in examples():
        before = deepcopy(evidence)
        packet = build_action_packet(
            question="reference", context_pack=evidence, public_requirements=requirements,
        )
        packet_errors = validate_action_packet(packet, evidence_items=evidence)
        projection, snapshot = project_patch_context(packet=packet, evidence_items=evidence)
        errors = validate_model_visible_projection(projection, snapshot=snapshot)
        class OfflineService:
            def get_docs_context(self, question, **kwargs):
                assert question == "reference"
                assert kwargs["allow_network"] is False
                return {
                    "status": "ok", "context_pack": deepcopy(evidence),
                    "public_requirements": requirements,
                }

        surface = current_docs_surface(env={})
        public = call_docs_tool_payload(
            "get_docs_context", {"question": "reference", "context_format": "patch_context"},
            OfflineService(), surface=surface,
        )
        jsonschema.validate(public, next(spec for spec in surface.tools if spec.name == "get_docs_context").output_schema)
        structured = _mcp_tool_result(mcp_types, public, text_fallback=False)
        fallback = _mcp_tool_result(mcp_types, public, text_fallback=True)
        assert structured.structuredContent == public
        assert json.loads(fallback.content[0].text) == public
        if evidence:
            assert public["sources"] == projection["sources"]
        else:
            assert public["result"] == "failure"
        encoded = json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        assert evidence == before
        assert not packet_errors and not errors, (name, packet_errors, errors)
        assert public["estimated_tokens"] == max(1, (len(encoded) + 3) // 4)
        assert fallback.content[0].text.encode() == encoded
        assert public["edit_ready"] is False
        rows.append({
            "example": name, "bytes": len(encoded),
            "estimated_tokens": public["estimated_tokens"],
            "completeness": public["completeness"],
            "validation": "PASS", "supplied_requirements": len(requirements),
            "retained_requirements": len(public.get("requirements", [])),
            "retained_sources": len(public.get("sources", [])),
        })
    assert rows[-1]["estimated_tokens"] > 2000
    assert rows[-1]["retained_sources"] == 18
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    measure()
