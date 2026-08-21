#!/usr/bin/env python3
"""Materialize v6 plus canonical normalized Project Docs path binding."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v6 = root / "scripts/_materialize_recoverable_docs_failures_v6.py"
exec(compile(v6.read_text(encoding="utf-8"), str(v6), "exec"), {"__name__": "__main__", "__file__": str(v6)})

path = root / "docmancer/docs/application/_project_docs_service_part03.py"
text = path.read_text(encoding="utf-8")
old = '''        current_by_path = {\n            item.get("path"): item\n            for item in indexed_sources\n            if item.get("path")\n        }\n        exact_document_fallback_used = False\n'''
new = '''        current_by_path = {\n            normalize_doc_path(item.get("path")): item\n            for item in indexed_sources\n            if item.get("path")\n        }\n        exact_document_fallback_used = False\n'''
if text.count(old) != 1:
    raise SystemExit(f"normalized current_by_path patch count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''        for chunk in chunks:\n            metadata_for_chunk = chunk.metadata or {}\n            chunk_path = metadata_for_chunk.get("project_doc_path") or metadata_for_chunk.get("source_path")\n            current_source = current_by_path.get(chunk_path)\n            if not current_source:\n                continue\n            if metadata_for_chunk.get("project_doc_content_hash") != current_source.get("content_hash"):\n                continue\n            if not lifecycle_allows(metadata_for_chunk, answer_lifecycle_intent):\n                continue\n            if self._looks_like_placeholder_search_result(chunk_path, chunk.text):\n                dropped_placeholder_chunks += 1\n                continue\n            safe_chunks.append(chunk)\n        chunks = safe_chunks\n'''
new = '''        for chunk in chunks:\n            metadata_for_chunk = chunk.metadata or {}\n            chunk_path = (\n                metadata_for_chunk.get("project_doc_path")\n                or metadata_for_chunk.get("source_path")\n            )\n            normalized_chunk_path = normalize_doc_path(chunk_path)\n            current_source = current_by_path.get(normalized_chunk_path)\n            if not current_source:\n                continue\n            if metadata_for_chunk.get("project_doc_content_hash") != current_source.get("content_hash"):\n                continue\n            if not lifecycle_allows(metadata_for_chunk, answer_lifecycle_intent):\n                continue\n            canonical_path = str(current_source.get("path") or chunk_path or "")\n            if self._looks_like_placeholder_search_result(canonical_path, chunk.text):\n                dropped_placeholder_chunks += 1\n                continue\n            # Retrieval/index internals may normalize path case. Once the chunk\n            # is rebound to the exact current catalog entry, restore that\n            # canonical identity before projection and evidence-path checks.\n            canonical_metadata = {\n                **metadata_for_chunk,\n                "project_doc_path": canonical_path,\n                "source_path": canonical_path,\n            }\n            safe_chunks.append(chunk.model_copy(update={"metadata": canonical_metadata}))\n        chunks = safe_chunks\n'''
if text.count(old) != 1:
    raise SystemExit(f"normalized safe chunk binding patch count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''        stale_paths = {item.get("path") for item in stale_sources}\n'''
new = '''        stale_paths = {\n            normalize_doc_path(item.get("path"))\n            for item in stale_sources\n            if item.get("path")\n        }\n'''
if text.count(old) != 1:
    raise SystemExit(f"normalized stale paths patch count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''                stale=((chunk.metadata or {}).get("project_doc_path") in stale_paths),\n'''
new = '''                stale=(\n                    normalize_doc_path((chunk.metadata or {}).get("project_doc_path"))\n                    in stale_paths\n                ),\n'''
if text.count(old) != 1:
    raise SystemExit(f"normalized stale check patch count={text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# Freeze canonical path preservation in the real public exact-document test.
gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''        assert {row["path_or_url"] for row in result["sources"]} == {\n            "docs/ADAPTIVE_TREASURE_CONTRACT.md"\n        }\n        assert "meet_type" in result["answer"]\n'''
new = '''        assert {row["path_or_url"] for row in result["sources"]} == {\n            "docs/ADAPTIVE_TREASURE_CONTRACT.md"\n        }\n        assert all(\n            "docs/adaptive_treasure_contract.md" not in row["path_or_url"]\n            for row in result["sources"]\n        )\n        assert "meet_type" in result["answer"]\n'''
if gate.count(old) != 1:
    raise SystemExit(f"canonical exact path test patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
