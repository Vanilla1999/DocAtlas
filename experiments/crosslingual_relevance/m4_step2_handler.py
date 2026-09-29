"""M4 Step 2 — real get_docs_context with dense retrieval.

Prove that the query reaches the dense backend through the real handler
and results reach service candidates. No monkeypatching of search results.

Uses the same corpus as Step 1 (M1.5 dev + Typer), indexed through the real
service with vectors enabled, then queried through get_docs_context via
observe_call (same pattern as M0 tests, but with vectors).

Usage:
    python -m experiments.crosslingual_relevance.m4_step2_handler
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from docmancer.core.config import DocmancerConfig, VectorStoreConfig

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.observer import observe_call

DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DENSE_DIM = 768

from experiments.crosslingual_relevance.m4_dense_candidates import (
    M15_DEV_TASKS, TYPER_TASKS, ALL_TASKS, PROJECTS,
)

GOLD_PHRASES_TYPER = (
    "only *CLI option* names to set the `False` value",
)


def _is_gold_source(source: dict, task: dict) -> bool:
    """Check if a source from get_docs_context matches the task's gold."""
    path = source.get("path_or_url") or source.get("source_path") or ""
    line_start = source.get("line_start")
    line_end = source.get("line_end")
    snippet = source.get("snippet") or ""
    for gold_path in task["gold_paths"]:
        if gold_path.split("/")[-1] in path.split("/")[-1] or gold_path in path or path in gold_path:
            if line_start is not None and line_end is not None:
                for gl_start, gl_end in task["gold_lines"]:
                    if line_start <= gl_end and line_end >= gl_start:
                        return True
            if task["id"].startswith("typer"):
                if any(p in snippet for p in GOLD_PHRASES_TYPER):
                    return True
            elif not line_start:
                return True
    return False


def main():
    tmp = Path(tempfile.mkdtemp(prefix="m4-step2-"))
    print(f"Working directory: {tmp}")

    # Build service with vectors enabled
    import scripts.run_project_docs_self_host_gate as gate

    state = tmp / "state"
    state.mkdir(parents=True, exist_ok=True)
    home_dir = tmp / "docatlas_home"
    home_dir.mkdir(parents=True, exist_ok=True)
    env = {key: str(state / key.lower()) for key in
           ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME')}
    env['DOCATLAS_HOME'] = str(home_dir)
    env.update(DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='1')
    for p in env.values():
        if p not in ('0', '1'):
            Path(p).mkdir(parents=True, exist_ok=True)

    with patch.dict(os.environ, env):
        config = gate.DocmancerConfig()
        config.index.db_path = str(state / 'index.db')
        config.index.extracted_dir = str(state / 'extracted')
        config.retrieval.default_mode = "dense"
        config.retrieval.max_sections_per_source = 20
        config.embeddings.provider = "fastembed"
        config.embeddings.model = DENSE_MODEL
        config.embeddings.dimensions = DENSE_DIM
        config.embeddings.sparse_model = None
        config.embeddings.cache = "/tmp/fastembed_cache"
        config.vector_store = VectorStoreConfig(
            provider="sqlite-vec",
            collection=f"m4step2_{uuid.uuid4().hex[:8]}",
        )

        # Ensure DocAtlas owns the home directory
        from docmancer.core.product_identity import ensure_owned_home
        ensure_owned_home(str(home_dir))

        service = gate.LibraryDocsService(
            config=config, config_source='explicit',
            registry=gate.LibraryRegistry(config.index.db_path),
            agent=gate.DocmancerAgent(config=config),
            job_tracker=gate.DocsJobTracker(),
        )

        # Index all projects with vectors
        _, _, manifest = load_protocol()
        project_roots = {}
        for project in PROJECTS:
            docs = documents_for(project, manifest)
            root = tmp / "projects" / project
            write_project(root, docs)
            print(f"  Indexing {project}...")
            result = service.sync_project_docs(str(root), with_vectors=True)
            if result.status != 'success':
                raise RuntimeError(f"index failed for {project}: {result.status}")
            project_roots[project] = str(root)

        print(f"\nAll {len(PROJECTS)} projects indexed with vectors.")

        # Run get_docs_context for all tasks via observe_call
        print(f"\n{'='*60}")
        print("STEP 2: Real get_docs_context (dense mode, with vectors)")
        print(f"{'='*60}")
        results = []
        for task in ALL_TASKS:
            project_root = project_roots[task["project"]]
            request = {
                "question": task["question"],
                "project_path": project_root,
                "scope": "all",
            }
            payload, _trace = observe_call(service, request)
            sources = payload.get("sources", [])
            gold_sources = []
            for i, source in enumerate(sources):
                if _is_gold_source(source, task):
                    gold_sources.append({
                        "rank": i + 1,
                        "path": source.get("path_or_url"),
                        "line_start": source.get("line_start"),
                        "line_end": source.get("line_end"),
                    })
            r = {
                "task_id": task["id"],
                "formulation": task["formulation"],
                "project": task["project"],
                "total_sources": len(sources),
                "gold_found": len(gold_sources) > 0,
                "gold_rank": gold_sources[0]["rank"] if gold_sources else None,
                "gold_sources": gold_sources,
                "answer_supported": payload.get("answer_supported"),
                "context_available": payload.get("context_available"),
            }
            results.append(r)
            status = "PASS" if r["gold_found"] else "FAIL"
            print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
                  f"gold_found={r['gold_found']} rank={r['gold_rank']} "
                  f"sources={r['total_sources']} "
                  f"context_available={r['context_available']}")

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        total = len(results)
        found = sum(1 for r in results if r["gold_found"])
        print(f"Gold found: {found}/{total}")
        by_formulation = {}
        for r in results:
            by_formulation.setdefault(r["formulation"], []).append(r)
        for formulation, fr in sorted(by_formulation.items()):
            f = sum(1 for r in fr if r["gold_found"])
            print(f"  {formulation}: {f}/{len(fr)}")

        # Save
        output = {"step2": results, "summary": {"total": total, "found": found}}
        out_path = Path("experiments/crosslingual_relevance/m4_step2_results.json")
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n",
                            encoding="utf-8")
        print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
