"""Trace DocAtlas indexing and querying its own project-doc manifest."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def compact(value: Any, limit: int = 20000) -> Any:
    raw = plain(value)
    text = json.dumps(raw, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return raw
    return {"truncated": True, "prefix": text[:limit]}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="docatlas-self-host-") as tmp:
        work = Path(tmp)
        os.environ["DOCMANCER_HOME"] = str(work / "home")
        os.environ["DOCMANCER_OFFLINE"] = "1"
        config = DocmancerConfig()
        config.index.db_path = str(work / "docmancer.db")
        config.index.extracted_dir = str(work / "extracted")
        service = LibraryDocsService(
            config=config,
            registry=LibraryRegistry(config.index.db_path),
            agent=DocmancerAgent(config=config),
            job_tracker=DocsJobTracker(),
        )

        sync = service.sync_project_docs(str(root), with_vectors=False)
        inspect = service.inspect_project_docs(str(root))
        direct_queries = {}
        for query in (
            "question planning",
            "project answer quality protocol",
            "storage mutation coordination",
            "Python version",
            "source types indexing",
        ):
            direct_queries[query] = compact(
                service.get_project_docs(str(root), query, tokens=1200, limit=5)
            )

        public_queries = {}
        for question in (
            "How does evidence selection choose which candidates are selected?",
            "What is the storage mutation coordination contract for cleanup and refresh?",
            "How do I run the project answer quality v4 protocol?",
        ):
            public_queries[question] = compact(call_docs_tool_payload(
                "get_docs_context",
                {
                    "question": question,
                    "project_path": str(root),
                    "mode": "project",
                    "delivery_strategy": "bounded_direct",
                    "packet_tokens": 800,
                },
                service,
            ))

        report = {
            "root": str(root),
            "manifest_exists": (root / "docatlas.project-docs.yaml").exists(),
            "sync": compact(sync),
            "inspect": compact(inspect),
            "direct_queries": direct_queries,
            "public_queries": public_queries,
        }
    Path("self-hosting-project-docs-debug.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("SELF_HOSTING_DEBUG=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
