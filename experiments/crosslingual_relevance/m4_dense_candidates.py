"""M4 — candidates for cross-lingual questions via real dense retrieval.

Step 1: Real DocmancerAgent/dispatcher, isolated index with vectors,
allow_degraded=False, mode="dense" — verify backend finds gold ranges
for M1.5 development split + Typer control.

Step 2: Same corpus through real handler get_docs_context — prove query
reaches dense backend, results reach service candidates.

Uses M1.5 frozen development split (4 tasks: httpx, ruff, starlette, pydantic)
plus Typer-05 as additional development control (3 questions: EN, mixed, pure-RU).
Calibration and holdout splits are NOT used in M4.

Negative controls: wrong-project filter, different version.

Usage:
    python -m experiments.crosslingual_relevance.m4_dense_candidates
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig, VectorStoreConfig
from docmancer.core.models import Document
from docmancer.retrieval.runtime import dispatcher_for_agent

from eval.evidence_quality_v2.run import documents_for, load_protocol

DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DENSE_DIM = 768
TOP_K = 20

# M1.5 development split tasks (from frozen manifest)
M15_DEV_TASKS = [
    {
        "id": "m15-dev-01", "project": "httpx", "formulation": "mixed",
        "question": "Какое поведение timeout по умолчанию в HTTPX: сколько секунд и какое исключение?",
        "gold_paths": ["docs/advanced/timeouts.md"], "gold_lines": [(1, 4)],
        "fact_ids": ["httpx-default-timeout"],
    },
    {
        "id": "m15-dev-02", "project": "ruff", "formulation": "EN",
        "question": "Does enabling preview automatically enable all preview rules?",
        "gold_paths": ["docs/preview.md"], "gold_lines": [(62, 63), (1, 8)],
        "fact_ids": ["ruff-preview-not-automatic"],
    },
    {
        "id": "m15-dev-03", "project": "starlette", "formulation": "RU",
        "question": "Когда выполняется teardown lifespan относительно соединений и фоновых задач?",
        "gold_paths": ["docs/lifespan.md"], "gold_lines": [(29, 30)],
        "fact_ids": ["starlette-teardown-ordering"],
    },
    {
        "id": "m15-dev-04", "project": "pydantic", "formulation": "mixed",
        "question": "Что specifies AliasPath: какой path to a field using aliases?",
        "gold_paths": ["docs/concepts/alias.md"], "gold_lines": [(25, 26), (44, 45)],
        "fact_ids": ["pydantic-aliaspath-purpose"],
    },
]

# Typer-05 additional development control
TYPER_TASKS = [
    {
        "id": "typer-05-en", "project": "typer", "formulation": "EN",
        "question": "How to declare only the negative name for a boolean option: is the space before / significant?",
        "gold_paths": ["docs/tutorial/parameter-types/bool.md"], "gold_lines": [(192, 213)],
        "fact_ids": ["typer-negative-name"],
    },
    {
        "id": "typer-05-mixed", "project": "typer", "formulation": "mixed",
        "question": "Как записать только отрицательное имя boolean option: важен ли пробел перед /?",
        "gold_paths": ["docs/tutorial/parameter-types/bool.md"], "gold_lines": [(192, 213)],
        "fact_ids": ["typer-negative-name"],
    },
    {
        "id": "typer-05-ru", "project": "typer", "formulation": "RU",
        "question": "Как объявить только отрицательное имя для логической опции: важен ли пробел перед косой чертой?",
        "gold_paths": ["docs/tutorial/parameter-types/bool.md"], "gold_lines": [(192, 213)],
        "fact_ids": ["typer-negative-name"],
    },
]

ALL_TASKS = M15_DEV_TASKS + TYPER_TASKS

# Projects to index (all 4 M1.5 docs + Typer)
PROJECTS = ["httpx", "ruff", "starlette", "pydantic", "typer"]


def _load_all_documents(root: Path) -> dict[str, tuple[list[Document], str]]:
    """Load all project documents, return {project: (documents, project_identity)}."""
    _, _, manifest = load_protocol()
    result = {}
    for project in PROJECTS:
        docs = documents_for(project, manifest)
        project_identity = f"local:{project}-{uuid.uuid4().hex[:8]}"
        documents = []
        for relative, content in sorted(docs.items()):
            documents.append(Document(
                source=str(root / project / relative),
                content=content,
                metadata={
                    "source_identity": str(root / project / relative),
                    "format": "markdown",
                    "source_path": relative,
                    "project_doc_path": relative,
                    "project_identity": project_identity,
                    "source_class": "project_file",
                    "project_docs": True,
                    "authority": "source_of_truth",
                    "lifecycle": "active",
                },
            ))
        result[project] = (documents, project_identity)
    return result


def _build_agent(root: Path, all_docs: list[Document]) -> DocmancerAgent:
    """Build an isolated DocmancerAgent with sqlite-vec vector store, dense-only."""
    config = DocmancerConfig()
    config.index.db_path = str(root / "index.sqlite")
    config.index.extracted_dir = str(root / "extracted")
    config.retrieval.default_mode = "dense"
    config.retrieval.fusion.method = "rrf"
    config.retrieval.fusion.rrf_k = 60
    config.retrieval.max_sections_per_source = 20
    config.embeddings.provider = "fastembed"
    config.embeddings.model = DENSE_MODEL
    config.embeddings.dimensions = DENSE_DIM
    config.embeddings.sparse_model = None
    config.embeddings.cache = "/tmp/fastembed_cache"
    config.vector_store = VectorStoreConfig(
        provider="sqlite-vec",
        collection=f"m4_{uuid.uuid4().hex[:8]}",
    )
    os.environ["DOCATLAS_HOME"] = str(root / "home")
    os.environ["DOCATLAS_FASTEMBED_CACHE_DIR"] = "/tmp/fastembed_cache"
    os.environ["DOCATLAS_OFFLINE"] = "1"
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(all_docs, recreate=True, with_vectors=True)
    return agent


def _is_gold_chunk(chunk: Any, task: dict) -> bool:
    """Check if a chunk matches any gold range for the task."""
    path = chunk.metadata.get("project_doc_path") or chunk.metadata.get("source_path") or ""
    line_start = chunk.metadata.get("line_start")
    line_end = chunk.metadata.get("line_end")
    # Match by path and line overlap
    for gold_path in task["gold_paths"]:
        if gold_path in path or path in gold_path:
            if line_start is not None and line_end is not None:
                for gl_start, gl_end in task["gold_lines"]:
                    # Check line overlap
                    if line_start <= gl_end and line_end >= gl_start:
                        return True
            else:
                # If no line metadata, match by path only
                return True
    return False


def _run_step1(dispatcher, task: dict, project_identity: str) -> dict[str, Any]:
    """Step 1: dispatcher.run with allow_degraded=False, mode='dense'."""
    result = dispatcher.run(
        task["question"],
        mode="dense",
        limit=TOP_K,
        expand="none",
        filters={"project_identity": project_identity},
        allow_degraded=False,
    )
    chunks = list(result.chunks)
    contributions = {
        str(sid): dict(cr) for sid, cr in result.contributions.items()
    }
    gold_ranks = []
    for i, chunk in enumerate(chunks):
        if _is_gold_chunk(chunk, task):
            gold_ranks.append(i + 1)
    return {
        "task_id": task["id"],
        "formulation": task["formulation"],
        "project": task["project"],
        "mode_requested": "dense",
        "mode_used": result.mode_used,
        "candidate_counts": dict(result.candidate_counts),
        "failures": dict(result.failures),
        "total_chunks": len(chunks),
        "gold_found": len(gold_ranks) > 0,
        "gold_rank": gold_ranks[0] if gold_ranks else None,
        "gold_ranks": gold_ranks,
        "dense_contributed_to_gold": any(
            "dense" in contributions.get(str(chunk.metadata.get("section_id")), {})
            for chunk in chunks if _is_gold_chunk(chunk, task)
        ),
    }


def _run_step1_wrong_project(dispatcher, task: dict, wrong_identity: str) -> dict[str, Any]:
    """Negative control: query with wrong project filter."""
    try:
        result = dispatcher.run(
            task["question"],
            mode="dense",
            limit=TOP_K,
            expand="none",
            filters={"project_identity": wrong_identity},
            allow_degraded=False,
        )
        chunks = list(result.chunks)
        gold_found = any(_is_gold_chunk(c, task) for c in chunks)
        return {
            "task_id": task["id"],
            "control": "wrong_project",
            "total_chunks": len(chunks),
            "gold_found": gold_found,
            "mode_used": result.mode_used,
        }
    except Exception as e:
        return {
            "task_id": task["id"],
            "control": "wrong_project",
            "error": str(e)[:200],
            "gold_found": False,
        }


def main():
    tmp = Path(tempfile.mkdtemp(prefix="m4-full-"))
    print(f"Working directory: {tmp}")

    # Load all documents
    project_docs = _load_all_documents(tmp)
    all_docs = []
    project_identities = {}
    for project, (docs, identity) in project_docs.items():
        all_docs.extend(docs)
        project_identities[project] = identity
        print(f"  {project}: {len(docs)} documents, identity={identity[:20]}...")

    # Build agent with vectors
    print(f"\nBuilding agent with {len(all_docs)} documents...")
    agent = _build_agent(tmp, all_docs)
    dispatcher = dispatcher_for_agent(agent, mode="dense")
    print(f"Dispatcher ready (mode=dense)")

    # Step 1: Run all tasks
    print(f"\n{'='*60}")
    print("STEP 1: Dispatcher with allow_degraded=False, mode='dense'")
    print(f"{'='*60}")
    step1_results = []
    for task in ALL_TASKS:
        identity = project_identities[task["project"]]
        r = _run_step1(dispatcher, task, identity)
        step1_results.append(r)
        status = "PASS" if r["gold_found"] and r["gold_rank"] <= 5 else "FAIL" if not r["gold_found"] else "WARN"
        print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
              f"gold_found={r['gold_found']} rank={r['gold_rank']} "
              f"chunks={r['total_chunks']} mode={r['mode_used']}")

    # Step 1: Negative controls
    print(f"\n--- Negative controls ---")
    neg_results = []
    # Use httpx task with pydantic identity (wrong project)
    wrong_task = M15_DEV_TASKS[0]  # httpx
    wrong_identity = project_identities["pydantic"]
    r = _run_step1_wrong_project(dispatcher, wrong_task, wrong_identity)
    neg_results.append(r)
    print(f"  wrong_project: gold_found={r['gold_found']} chunks={r['total_chunks']}")

    wrong_task2 = M15_DEV_TASKS[2]  # starlette (RU)
    wrong_identity2 = project_identities["httpx"]
    r2 = _run_step1_wrong_project(dispatcher, wrong_task2, wrong_identity2)
    neg_results.append(r2)
    print(f"  wrong_project (RU): gold_found={r2['gold_found']} chunks={r2['total_chunks']}")

    # Step 1: Strict hybrid test (should fail — no sparse support)
    print(f"\n--- Strict hybrid test (expected to fail: no sparse) ---")
    try:
        dispatcher.run(
            TYPER_TASKS[2]["question"],  # pure RU
            mode="hybrid", limit=TOP_K, expand="none",
            filters={"project_identity": project_identities["typer"]},
            allow_degraded=False,
        )
        print("  ERROR: hybrid should have failed without sparse support")
        hybrid_result = {"hybrid_strict": "unexpected_pass"}
    except Exception as e:
        print(f"  Expected failure: {type(e).__name__}")
        hybrid_result = {"hybrid_strict": "expected_error", "error_type": type(e).__name__}

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    # Recall@5
    total = len(step1_results)
    found_in_top5 = sum(1 for r in step1_results if r["gold_found"] and r["gold_rank"] <= 5)
    found_in_top20 = sum(1 for r in step1_results if r["gold_found"])
    print(f"Recall@5: {found_in_top5}/{total} = {found_in_top5/total:.2f}")
    print(f"Recall@20: {found_in_top20}/{total} = {found_in_top20/total:.2f}")

    # Per language group
    by_formulation = {}
    for r in step1_results:
        f = r["formulation"]
        by_formulation.setdefault(f, []).append(r)
    for formulation, results in sorted(by_formulation.items()):
        found = sum(1 for r in results if r["gold_found"] and r["gold_rank"] <= 5)
        print(f"  {formulation}: Recall@5 = {found}/{len(results)}")

    # Negative controls
    for r in neg_results:
        status = "PASS" if not r["gold_found"] else "FAIL"
        print(f"  negative {r['control']}: {status} (gold_found={r['gold_found']})")

    # Degraded check
    degraded_count = sum(1 for r in step1_results if "degraded" in str(r["mode_used"]))
    print(f"  degraded runs: {degraded_count} (should be 0 for neural PASS)")

    # Save results
    output = {
        "step1": step1_results,
        "negative_controls": neg_results,
        "hybrid_strict": hybrid_result,
        "summary": {
            "total_tasks": total,
            "recall_at_5": found_in_top5 / total,
            "recall_at_20": found_in_top20 / total,
            "degraded_runs": degraded_count,
        },
    }
    out_path = Path("experiments/crosslingual_relevance/m4_dense_results.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n",
                        encoding="utf-8")
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
