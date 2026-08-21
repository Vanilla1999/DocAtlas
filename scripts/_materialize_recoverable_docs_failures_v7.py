#!/usr/bin/env python3
"""Materialize v6 and print canonical exact-document index metadata."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v6 = root / "scripts/_materialize_recoverable_docs_failures_v6.py"
exec(compile(v6.read_text(encoding="utf-8"), str(v6), "exec"), {"__name__": "__main__", "__file__": str(v6)})

gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''        service, project = _service(Path(tmp))\n        original_query = service.project_docs.query_project_docs\n        service.project_docs.query_project_docs = lambda *args, **kwargs: []\n'''
new = '''        service, project = _service(Path(tmp))\n        agent = service._agent_instance()\n        indexed_rows = list(agent.store.list_sections_for_embedding())\n        print("EXACT_INDEX_ROWS=" + json.dumps([\n            {\n                "source": row.get("source"),\n                "source_path": row.get("source_path"),\n                "project_path": row.get("project_path"),\n                "source_class": row.get("source_class"),\n                "title": row.get("title"),\n                "anchor": row.get("anchor"),\n            }\n            for row in indexed_rows\n        ], indent=2, default=str))\n        unique_sources = sorted({str(row.get("source") or "") for row in indexed_rows if row.get("source")})\n        print("EXACT_SOURCE_METADATA=" + json.dumps({\n            source: agent.store.source_metadata(source) for source in unique_sources\n        }, indent=2, default=str))\n        from docmancer.docs.application._project_docs_service_part03 import _exact_document_index_chunks\n        exact_requirements = build_requirements(\n            "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type.",\n            required_evidence_paths=("docs/ADAPTIVE_TREASURE_CONTRACT.md",),\n            profile="project_document_answer",\n        )\n        direct_fallback = _exact_document_index_chunks(\n            agent, root=project, evidence_path="docs/ADAPTIVE_TREASURE_CONTRACT.md",\n            requirements=exact_requirements,\n        )\n        print("EXACT_DIRECT_FALLBACK=" + json.dumps([\n            {"source": row.source, "chunk_index": row.chunk_index, "text": row.text, "metadata": row.metadata}\n            for row in direct_fallback\n        ], indent=2, default=str))\n        original_query = service.project_docs.query_project_docs\n        service.project_docs.query_project_docs = lambda *args, **kwargs: []\n'''
if gate.count(old) != 1:
    raise SystemExit(f"exact fallback diagnostic patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
