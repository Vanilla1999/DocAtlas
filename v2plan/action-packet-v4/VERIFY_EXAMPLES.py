"""Offline reproducible measurements of the integrated patch projection.

Run from the integration root with PYTHONPATH=. using the existing interpreter.
No live retrieval, provider calls, index writes or corpus expansion.
"""
from copy import deepcopy
import hashlib
import json

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application.model_visible_projection import (
    project_patch_context, validate_model_visible_projection,
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
        encoded = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        assert evidence == before
        assert not packet_errors and not errors, (name, packet_errors, errors)
        assert projection["estimated_tokens"] == max(1, (len(encoded) + 3) // 4)
        assert projection["edit_ready"] is False
        rows.append({
            "example": name, "bytes": len(encoded),
            "estimated_tokens": projection["estimated_tokens"],
            "completeness": projection["completeness"],
            "validation": "PASS", "supplied_requirements": len(requirements),
            "retained_requirements": len(projection.get("requirements", [])),
            "retained_sources": len(projection.get("sources", [])),
        })
    assert rows[-1]["estimated_tokens"] > 2000
    assert rows[-1]["retained_sources"] == 18
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    measure()
