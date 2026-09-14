"""Production-path regressions for budgeted docs-context recovery targets."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.interfaces.host_context import SourceReadController
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource


def _real_service(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="recovery-smoke"\nversion="0.1"\n')
    path = tmp_path / "docs/polling.md"
    body = ["# Polling", "", "Retry only after a terminal status is observed.", ""]
    body.extend(f"Polling context line {index}." for index in range(1, 18))
    body.append("Job polling uses docs_status to inspect progress until terminal status.")
    body.extend(f"Additional polling context {index}." for index in range(18, 36))
    path.write_text("\n".join(body) + "\n")
    (tmp_path / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n  - path: docs/polling.md\n    role: runbook\n"
        "    scope: project\n    authority: source_of_truth\n    status: active\n"
        "    description: Polling lifecycle\n"
    )
    config = DocmancerConfig()
    config.index.provider = "sqlite"
    config.index.db_path = str(tmp_path / "state/index.db")
    config.index.extracted_dir = str(tmp_path / "state/extracted")
    service = LibraryDocsService(config=config, config_source="explicit")
    assert service.sync_project_docs(str(tmp_path), with_vectors=False).status == "success"
    return service


def test_final_public_handler_preserves_quality_and_usable_reference(tmp_path):
    service = _real_service(tmp_path)
    args = {
        "question": "How does docs_status polling progress work?",
        "lookup_queries": ["docs_status polling progress"],
        "project_path": str(tmp_path),
        "scope": "all",
    }
    payload = call_docs_tool_payload("get_docs_context", args, service)
    assert payload["kind"] == "docs_context"
    assert payload["context_quality"]["status"] in {"unverified", "partial"}
    assert len(payload["read_next"]) == 1
    target = payload["read_next"][0]
    assert target["reason"] in {"inspect_source_context", "requested_part_missing"}
    assert target["snapshot_sha256"].startswith("sha256:")
    assert docs_context_budget_tokens(payload) <= 800

    read = json.loads(read_docs_resource(target["source_uri"], service)["text"])
    assert read["line_start"] == target["line_start"]
    assert read["line_end"] <= target["line_end"]
    assert read["content_sha256"] == target["snapshot_sha256"]

    service = _real_service(tmp_path / "second")
    payload = call_docs_tool_payload("get_docs_context", {
        **args, "project_path": str(tmp_path / "second"),
    }, service)
    target = payload["read_next"][0]
    controller = SourceReadController(
        payload,
        requested_facts={"rule": "What rule appears around the polling evidence?"},
        read_resource=lambda uri: json.loads(read_docs_resource(uri, service)["text"]),
    )
    accepted = controller.read(target["source_uri"], missing_fact_id="rule")
    assert accepted["status"] in {"complete", "truncated"}


class _Reader:
    def __init__(self, *, fail_range: bool = False):
        self.fail_range = fail_range
        self.ranges = []

    def issue(self, reference, *, uri=None):
        return uri

    def issue_range(self, reference, *, line_start, line_end, uri=None):
        self.ranges.append((reference.path, line_start, line_end, uri))
        return None if self.fail_range else uri


class _ContextApp:
    def __init__(self, raw, reader):
        self.raw = raw
        self.source_reader = reader
        self.unified_context = self

    def get_docs_context(self, *args, **kwargs):
        return deepcopy(self.raw)


def _candidate(path: str, content: str, *, query_id: str, line_start: int, stable_id: str):
    digest = "sha256:" + hashlib.sha256((path + content).encode()).hexdigest()
    catalog = "sha256:" + hashlib.sha256(("catalog:" + path).encode()).hexdigest()
    return {
        "stable_id": stable_id,
        "source_class": "project_doc",
        "path": path,
        "heading_path": "Recovery",
        "content": content,
        "project_identity": "project:recovery",
        "line_start": line_start,
        "line_end": line_start + content.count("\n"),
        "authority": "source_of_truth",
        "doc_scope": "project",
        "lifecycle_status": "active",
        "freshness": "current",
        "index_freshness": "synchronized",
        "risk_flags": [],
        "_source_snapshot_sha256": digest,
        "_source_catalog_hash": catalog,
        "retrieval_query_ids": [query_id],
        "retrieval_query_matches": {
            query_id: {
                "qualified": True,
                "mode": "and",
                "query_text": "export identifiers" if query_id == "query-original" else "complete runnable example",
            }
        },
    }


def _raw_recovery_fixture():
    direct = (
        "Background context before the direct explanation.\n\n"
        "The export operation preserves original identifiers.\n\n"
        "Background context after the direct explanation."
    )
    example = "```python\n" + "# complete runnable example for export identifiers\n" * 180 + "export_identifiers()\n```"
    return {
        "status": "success",
        "mode_selected": "project",
        "project_identity": "project:recovery",
        "context_pack": [
            _candidate("docs/direct.md", direct, query_id="query-original", line_start=20, stable_id="direct"),
            _candidate("docs/example.md", example, query_id="query-example", line_start=100, stable_id="example"),
        ],
        "documentation_query_plan": {
            "original_question": "How does the export operation preserve original identifiers?",
            "query_ids": ["query-original", "query-example"],
            "required_query_ids": ["query-original", "query-example"],
            "public_query_ids": ["query-original", "query-example"],
            "queries": [
                {"query_id": "query-original", "text": "export identifiers", "origin": "original"},
                {"query_id": "query-example", "text": "complete runnable example", "origin": "host_lookup"},
            ],
        },
        "retrieval_diagnostics": {},
    }


def test_omitted_candidate_can_supply_read_target_without_becoming_evidence():
    reader = _Reader()
    service = _ContextApp(_raw_recovery_fixture(), reader)
    payload = handle_context_tool("get_docs_context", {
        "question": "How does the export operation preserve original identifiers?",
        "project_path": "/repo",
        "scope": "all",
    }, service)
    assert payload["kind"] == "docs_context"
    assert docs_context_budget_tokens(payload) <= 800
    assert len(payload["read_next"]) == 1
    target = payload["read_next"][0]
    assert target["path"] in {"docs/direct.md", "docs/example.md"}
    assert all(source["path_or_url"] != target["path"] for source in payload["sources"]) or target["path"] == "docs/direct.md"
    if target["path"] == "docs/example.md":
        assert all(source["path_or_url"] != "docs/example.md" for source in payload["sources"])
    assert reader.ranges


def test_binding_failure_removes_dead_read_next_and_reports_cause():
    reader = _Reader(fail_range=True)
    service = _ContextApp(_raw_recovery_fixture(), reader)
    payload = handle_context_tool("get_docs_context", {
        "question": "How does the export operation preserve original identifiers?",
        "project_path": "/repo",
        "scope": "all",
    }, service)
    assert payload["read_next"] == []
    assert "source_unavailable" in payload["context_quality"]["reasons"]
    assert docs_context_budget_tokens(payload) <= 800
