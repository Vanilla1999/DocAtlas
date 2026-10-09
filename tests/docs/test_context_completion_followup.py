"""Real-corpus completion: first-packet facts and explicitly consumed recovery."""
from copy import deepcopy
import json

from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.joint_context_candidates import source_options
from docmancer.docs.application.joint_context_selection import _finish
from docmancer.docs.application.model_visible_projection import (
    _snapshot_entry, docs_context_budget_tokens, validate_model_visible_projection,
)
from docmancer.mcp.docs_server import read_docs_resource


def test_shared_heading_metadata_does_not_evict_canonical_text(tmp_path):
    """The actual serializer must remove duplicate labels, not canonical text."""
    from unittest.mock import patch
    from docmancer.docs.application import joint_context_selection
    _, _, manifest = load_protocol()
    root = tmp_path / "project"
    write_project(root, documents_for("fastapi", manifest))
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        with patch.object(joint_context_selection, "select_joint_context",
                          side_effect=lambda p, b, r, **kw: (p, b)):
            payload, trace = observe_call(service, {
                "question": "At what point in the response lifecycle are FastAPI background tasks executed?",
                "project_path": str(root), "scope": "all",
            })
    snapshot = deepcopy(trace["snapshot"])
    row = payload["sources"][0]
    _, intro = source_options(row, snapshot[row["evidence_id"]]["source"])
    assert intro is not None
    draft = deepcopy(payload)
    draft["read_next"] = []
    for source in draft["sources"]:
        source.pop("source_uri", None)
    public, original = intro
    draft["sources"].append(public)
    snapshot[public["evidence_id"]] = _snapshot_entry(original, public)
    retrieval = trace["stages"]["projector_inputs"][0]
    full = _finish(draft, snapshot, retrieval, "", 10000)
    assert full is not None
    limit = docs_context_budget_tokens(full[0]) - 1
    result = _finish(draft, snapshot, retrieval, "", limit)
    assert result is not None
    out, bindings, _ = result
    assert docs_context_budget_tokens(out) <= limit
    assert [s["snippet"] for s in out["sources"]] == [s["snippet"] for s in draft["sources"]]
    assert validate_model_visible_projection(out, snapshot=bindings, max_tokens=limit) == []


def test_priority_rule_available_in_first_packet_or_one_registered_read(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c["id"] == "mkdocs-05")
    docs = documents_for("mkdocs", manifest)
    root = tmp_path / "project"
    write_project(root, docs)
    fact = case["required_claims"][0]["witness_sets"][0]["parts"][0]["text"]
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        payload, trace = observe_call(service, {
            "question": case["question"], "project_path": str(root), "scope": "all",
        })
        assert audit_payload(payload, trace["snapshot"], root) == []
        first = [s["snippet"] for s in payload.get("sources", [])]
        reads = []
        if not any(fact in text for text in first):
            assert len(payload["read_next"]) == 1
            target = payload["read_next"][0]
            read = json.loads(read_docs_resource(target["source_uri"], service)["text"])
            assert read["status"] in {"complete", "truncated"}
            assert read["content_sha256"] == target["snapshot_sha256"]
            raw = docs[target["path"]]
            assert read["snippet"] in "\n".join(raw.splitlines()[read["line_start"]-1:read["line_end"]])
            reads.append(read["snippet"])
        assert any(fact in text for text in first + reads), {"payload": payload, "reads": reads}
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False
