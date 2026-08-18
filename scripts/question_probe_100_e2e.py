"""Run the 100-question corpus against the real repository manifest and public MCP surface."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import runpy
import tempfile
from typing import Any

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def _service(root: Path, work: Path) -> LibraryDocsService:
    os.environ["DOCMANCER_HOME"] = str(work / "home")
    os.environ["DOCMANCER_OFFLINE"] = "1"
    config = DocmancerConfig()
    config.index.db_path = str(work / "docmancer.db")
    config.index.extracted_dir = str(work / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def _source_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source in payload.get("sources") or []:
        rows.append({
            "path": source.get("path_or_url") or source.get("path"),
            "section": source.get("section") or source.get("heading_path"),
            "authority": source.get("authority"),
            "snippet": str(source.get("snippet") or source.get("content") or "")[:240],
        })
    return rows


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cases = tuple(runpy.run_path(str(root / "scripts" / "question_probe_100.py"))["CASES"])
    with tempfile.TemporaryDirectory(prefix="docatlas-question-e2e-") as tmp:
        work = Path(tmp)
        service = _service(root, work)
        sync = service.sync_project_docs(str(root), with_vectors=False)
        if sync.status != "success":
            raise RuntimeError(f"project-doc sync failed: {sync.status}: {sync.message}")

        results: list[dict[str, Any]] = []
        for case in cases:
            payload = call_docs_tool_payload(
                "get_docs_context",
                {
                    "question": case["question"],
                    "project_path": str(root),
                    "mode": "project",
                    "delivery_strategy": "bounded_direct",
                    "max_tokens": 800,
                },
                service,
            )
            payload = payload or {}
            status = str(payload.get("status") or "missing")
            expected_abstain = case["expectation"] == "abstain"
            desired_match = status != "ok" if expected_abstain else status == "ok"
            results.append({
                **case,
                "status": status,
                "desired_match": desired_match,
                "kind": payload.get("kind"),
                "reason_code": payload.get("reason_code"),
                "missing": payload.get("missing"),
                "answer_available": payload.get("answer_available"),
                "sources": _source_summary(payload),
            })

    status_counts = Counter(row["status"] for row in results)
    category_summary: dict[str, Counter[str]] = defaultdict(Counter)
    for row in results:
        category_summary[row["category"]][row["status"]] += 1
        category_summary[row["category"]]["total"] += 1
        category_summary[row["category"]]["desired_match" if row["desired_match"] else "desired_mismatch"] += 1
    report = {
        "schema_version": "docatlas-question-e2e-probe-v1",
        "total": len(results),
        "status_counts": dict(status_counts),
        "desired_matches": sum(row["desired_match"] for row in results),
        "desired_mismatches": sum(not row["desired_match"] for row in results),
        "category_summary": {key: dict(value) for key, value in sorted(category_summary.items())},
        "mismatches": [row for row in results if not row["desired_match"]],
        "results": results,
    }
    Path("question-probe-100-e2e-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("QUESTION_E2E_PROBE_SUMMARY=" + json.dumps({
        key: report[key]
        for key in ("total", "status_counts", "desired_matches", "desired_mismatches", "category_summary")
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
