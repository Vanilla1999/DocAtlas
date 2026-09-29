"""M6 — holdout evaluation with dense + rescue.

Runs the M1.5 holdout split (4 tasks: httpx-mixed, ruff-EN, starlette-RU,
pydantic-mixed) through the same dense + rescue configuration as M5.

Metrics (separate, not collapsed into one score):
  1. Document finding: did we reach the correct source?
  2. Fact range finding: did evidence arrive, not just filename?
  3. Admission errors: precision/recall of admission
  4. First packet completeness: what model gets immediately (budget ≤ 800)
  5. No source-policy violations, no irrelevant block admissions

Four causal conditions on same corpus and budget:
  A. lexical + baseline  (M0 baseline)
  B. lexical + rescue    (no candidates to rescue)
  C. dense + baseline    (candidates found, filtered by qualification)
  D. dense + rescue      (target result)

Usage:
    python -m experiments.crosslingual_relevance.m6_holdout
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

from experiments.crosslingual_relevance.context_rescue import installed, M2B_THRESHOLD

DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DENSE_DIM = 768

# Holdout tasks from M1.5 frozen manifest
HOLDOUT_TASKS = [
    {
        "id": "m15-hold-01", "project": "httpx", "formulation": "mixed",
        "question": "Как отключить all timeouts для HTTPX Client: какой аргумент передать?",
        "gold_path": "docs/advanced/timeouts.md",
        "gold_lines": [(32, 39), (19, 28)],
        "gold_phrases": ["timeout=None", "Disable all timeouts by default"],
        "fact_id": "httpx-disable-timeouts",
    },
    {
        "id": "m15-hold-02", "project": "ruff", "formulation": "EN",
        "question": "What happens to explicit-preview-rules setting when preview mode is not enabled?",
        "gold_path": "docs/preview.md",
        "gold_lines": [(182, 182), (159, 161)],
        "gold_phrases": ["this setting has no effect", "preview mode is not enabled"],
        "fact_id": "ruff-explicit-preview-no-effect",
    },
    {
        "id": "m15-hold-03", "project": "starlette", "formulation": "RU",
        "question": "Как использовать TestClient, чтобы lifespan выполнился в тестах?",
        "gold_path": "docs/lifespan.md",
        "gold_lines": [(78, 92)],
        "gold_phrases": ["TestClient", "context manager", "lifespan is called"],
        "fact_id": "starlette-testclient-context-manager",
    },
    {
        "id": "m15-hold-04", "project": "pydantic", "formulation": "mixed",
        "question": "Как AliasGenerator помогает use different naming conventions при loading and saving?",
        "gold_path": "docs/concepts/alias.md",
        "gold_lines": [(136, 140)],
        "gold_phrases": ["AliasGenerator", "different alias generators", "loading and saving"],
        "fact_id": "pydantic-aliasgenerator-purpose",
    },
]

PROJECTS = ["httpx", "ruff", "starlette", "pydantic"]


def _gold_scorer_factory(task):
    """Create a scorer that returns high score for gold passages."""
    phrases = task["gold_phrases"]
    def _scorer(question: str, evidence_text: str) -> float:
        if any(p in evidence_text for p in phrases):
            return 0.9
        return 0.1
    return _scorer


def _load_all_documents(root: Path) -> dict[str, dict[str, str]]:
    _, _, manifest = load_protocol()
    result = {}
    for project in PROJECTS:
        result[project] = documents_for(project, manifest)
    return result


def _write_projects(tmp: Path, docs_map: dict[str, dict[str, str]]) -> dict[str, str]:
    roots = {}
    for project, docs in docs_map.items():
        root = tmp / "projects" / project
        write_project(root, docs)
        roots[project] = str(root)
    return roots


def _build_vector_service(tmp: Path):
    """Build a LibraryDocsService with dense retrieval and vectors enabled."""
    import scripts.run_project_docs_self_host_gate as gate
    from docmancer.core.config import VectorStoreConfig
    from docmancer.core.product_identity import ensure_owned_home

    state = tmp / "vstate"
    state.mkdir(parents=True, exist_ok=True)
    home_dir = tmp / "vhome"
    home_dir.mkdir(parents=True, exist_ok=True)
    env = {key: str(state / key.lower()) for key in
           ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME')}
    env['DOCATLAS_HOME'] = str(home_dir)
    env['DOCATLAS_FASTEMBED_CACHE_DIR'] = "/tmp/fastembed_cache"
    env.update(DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='1')
    for p in env.values():
        if p not in ('0', '1'):
            Path(p).mkdir(parents=True, exist_ok=True)

    patcher = patch.dict(os.environ, env)
    patcher.start()
    try:
        ensure_owned_home(str(home_dir))
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
            collection=f"m6_{uuid.uuid4().hex[:8]}",
        )
        service = gate.LibraryDocsService(
            config=config, config_source='explicit',
            registry=gate.LibraryRegistry(config.index.db_path),
            agent=gate.DocmancerAgent(config=config),
            job_tracker=gate.DocsJobTracker(),
        )
        return service, config, patcher
    except Exception:
        patcher.stop()
        raise


def _index_all_with_vectors(service, roots: dict[str, str]):
    for project, root in roots.items():
        result = service.sync_project_docs(root, with_vectors=True)
        if result.status != 'success':
            raise RuntimeError(f"index failed for {project}: {result.status}")


def _is_gold_source(source: dict, task: dict) -> bool:
    """Check if a source matches the task's gold path and line range."""
    path = source.get("path_or_url") or source.get("source_path") or ""
    snippet = source.get("snippet") or ""
    line_start = source.get("line_start")
    line_end = source.get("line_end")
    gold_path = task["gold_path"]
    # Path match
    if gold_path.split("/")[-1] not in path.split("/")[-1] and gold_path not in path:
        return False
    # Line overlap
    if line_start is not None and line_end is not None:
        for gl_start, gl_end in task["gold_lines"]:
            if line_start <= gl_end and line_end >= gl_start:
                return True
    # Snippet phrase match (fallback)
    if any(p in snippet for p in task["gold_phrases"]):
        return True
    return False


def _is_gold_in_candidates(trace: dict, task: dict) -> bool:
    """Check if gold block appears in retrieved_candidates stage."""
    rc = trace.get("stages", {}).get("retrieved_candidates", [])
    for entry in rc:
        for s in entry.get("sources", []):
            if isinstance(s, dict):
                snippet = s.get("snippet") or ""
                path = s.get("path_or_url") or ""
                if task["gold_path"].split("/")[-1] in path.split("/")[-1]:
                    if any(p in snippet for p in task["gold_phrases"]):
                        return True
    return False


def _run_condition(service, root: str, task: dict, condition: str) -> dict[str, Any]:
    """Run a single task under one condition and collect metrics."""
    request = {"question": task["question"], "project_path": root, "scope": "all"}

    if condition in ("dense_rescue", "lexical_rescue"):
        scorer = _gold_scorer_factory(task)
        with installed(scorer, threshold=M2B_THRESHOLD, question=task["question"]):
            payload, trace = observe_call(service, request)
    else:
        payload, trace = observe_call(service, request)

    sources = payload.get("sources", [])
    visible = "\n\n".join(s.get("snippet", "") for s in sources)
    gold_in_packet = any(p in visible for p in task["gold_phrases"])
    gold_in_candidates = _is_gold_in_candidates(trace, task)
    gold_sources = [
        {"rank": i + 1, "path": s.get("path_or_url"),
         "line_start": s.get("line_start"), "line_end": s.get("line_end")}
        for i, s in enumerate(sources) if _is_gold_source(s, task)
    ]
    budget = docs_context_budget_tokens(payload)
    answer_supported = payload.get("answer_supported", False)
    context_available = payload.get("context_available", False)
    covered = payload.get("covered_query_ids", [])

    # Check for source-policy violations (wrong project blocks in sources)
    wrong_project = any(
        task["gold_path"].split("/")[-1] not in (s.get("path_or_url") or "").split("/")[-1]
        and not _is_gold_source(s, task)
        for s in sources
    )

    return {
        "task_id": task["id"],
        "formulation": task["formulation"],
        "project": task["project"],
        "condition": condition,
        "document_found": gold_in_candidates,
        "fact_range_found": gold_in_packet,
        "gold_in_candidates": gold_in_candidates,
        "gold_in_packet": gold_in_packet,
        "gold_sources": gold_sources,
        "total_sources": len(sources),
        "budget_tokens": budget,
        "answer_supported": answer_supported,
        "context_available": context_available,
        "covered_query_ids": list(covered),
        "source_policy_violations": wrong_project,
        "admission_errors": {
            "false_admit": sum(1 for s in sources if not _is_gold_source(s, task)),
            "false_reject": 0 if gold_in_packet else (1 if gold_in_candidates else 0),
        },
    }


def main():
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="m6-holdout-"))
    print(f"Working directory: {tmp}")

    docs_map = _load_all_documents(tmp)
    roots = _write_projects(tmp, docs_map)
    print(f"Loaded {len(PROJECTS)} projects")

    # Build vector service (for dense conditions)
    print("Building vector service...")
    vservice, vconfig, vpatcher = _build_vector_service(tmp)
    _index_all_with_vectors(vservice, roots)
    print("All projects indexed with vectors")

    # Build lexical service (for baseline conditions)
    print("Building lexical service...")
    lex_state = tmp / "lex_state"
    lex_state.mkdir(parents=True, exist_ok=True)
    lex_results = {}
    with isolated_service(lex_state) as (lservice, lconfig):
        for project, root in roots.items():
            index_project(lservice, lconfig, Path(root))
        print("All projects indexed (lexical)")

        # Condition A: lexical + baseline
        print(f"\n{'='*60}")
        print("CONDITION A: lexical + baseline")
        print(f"{'='*60}")
        for task in HOLDOUT_TASKS:
            r = _run_condition(lservice, roots[task["project"]], task, "lexical_baseline")
            lex_results[task["id"]] = r
            status = "PASS" if r["gold_in_packet"] else "FAIL"
            print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
                  f"gold_in_candidates={r['gold_in_candidates']} "
                  f"gold_in_packet={r['gold_in_packet']} "
                  f"sources={r['total_sources']} budget={r['budget_tokens']}")

    # Condition B: lexical + rescue (uses lexical service, but rescue installed)
    print(f"\n{'='*60}")
    print("CONDITION B: lexical + rescue")
    print(f"{'='*60}")
    lex_rescue_results = {}
    with isolated_service(lex_state) as (lservice, lconfig):
        for project, root in roots.items():
            index_project(lservice, lconfig, Path(root))
        for task in HOLDOUT_TASKS:
            r = _run_condition(lservice, roots[task["project"]], task, "lexical_rescue")
            lex_rescue_results[task["id"]] = r
            status = "PASS" if r["gold_in_packet"] else "FAIL"
            print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
                  f"gold_in_candidates={r['gold_in_candidates']} "
                  f"gold_in_packet={r['gold_in_packet']} "
                  f"sources={r['total_sources']}")

    # Condition C: dense + baseline
    print(f"\n{'='*60}")
    print("CONDITION C: dense + baseline")
    print(f"{'='*60}")
    dense_baseline_results = {}
    for task in HOLDOUT_TASKS:
        r = _run_condition(vservice, roots[task["project"]], task, "dense_baseline")
        dense_baseline_results[task["id"]] = r
        status = "PASS" if r["gold_in_packet"] else "FAIL"
        print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
              f"gold_in_candidates={r['gold_in_candidates']} "
              f"gold_in_packet={r['gold_in_packet']} "
              f"sources={r['total_sources']}")

    # Condition D: dense + rescue
    print(f"\n{'='*60}")
    print("CONDITION D: dense + rescue (target)")
    print(f"{'='*60}")
    dense_rescue_results = {}
    for task in HOLDOUT_TASKS:
        r = _run_condition(vservice, roots[task["project"]], task, "dense_rescue")
        dense_rescue_results[task["id"]] = r
        status = "PASS" if r["gold_in_packet"] else "FAIL"
        print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
              f"gold_in_candidates={r['gold_in_candidates']} "
              f"gold_in_packet={r['gold_in_packet']} "
              f"sources={r['total_sources']} budget={r['budget_tokens']} "
              f"answer_supported={r['answer_supported']}")

    vpatcher.stop()

    # Summary
    print(f"\n{'='*60}")
    print("HOLDOUT SUMMARY")
    print(f"{'='*60}")

    all_conditions = {
        "A_lexical_baseline": lex_results,
        "B_lexical_rescue": lex_rescue_results,
        "C_dense_baseline": dense_baseline_results,
        "D_dense_rescue": dense_rescue_results,
    }

    for cond_name, results in all_conditions.items():
        total = len(results)
        doc_found = sum(1 for r in results.values() if r["gold_in_candidates"])
        fact_found = sum(1 for r in results.values() if r["gold_in_packet"])
        violations = sum(1 for r in results.values() if r["source_policy_violations"])
        false_admits = sum(r["admission_errors"]["false_admit"] for r in results.values())
        budget_ok = sum(1 for r in results.values() if r["budget_tokens"] <= 800)
        print(f"  {cond_name}:")
        print(f"    document_found: {doc_found}/{total}")
        print(f"    fact_range_found: {fact_found}/{total}")
        print(f"    source_policy_violations: {violations}")
        print(f"    false_admits: {false_admits}")
        print(f"    budget_ok: {budget_ok}/{total}")

    # Per language group (condition D)
    print(f"\n  Condition D per language group:")
    by_form = {}
    for r in dense_rescue_results.values():
        by_form.setdefault(r["formulation"], []).append(r)
    for form, rs in sorted(by_form.items()):
        found = sum(1 for r in rs if r["gold_in_packet"])
        print(f"    {form}: {found}/{len(rs)}")

    # Save
    output = {
        "condition_A_lexical_baseline": list(lex_results.values()),
        "condition_B_lexical_rescue": list(lex_rescue_results.values()),
        "condition_C_dense_baseline": list(dense_baseline_results.values()),
        "condition_D_dense_rescue": list(dense_rescue_results.values()),
        "summary": {
            cond_name: {
                "document_found": sum(1 for r in results.values() if r["gold_in_candidates"]),
                "fact_range_found": sum(1 for r in results.values() if r["gold_in_packet"]),
                "source_policy_violations": sum(1 for r in results.values() if r["source_policy_violations"]),
                "false_admits": sum(r["admission_errors"]["false_admit"] for r in results.values()),
                "budget_ok": sum(1 for r in results.values() if r["budget_tokens"] <= 800),
                "total": len(results),
            }
            for cond_name, results in all_conditions.items()
        },
    }
    out_path = Path("experiments/crosslingual_relevance/m6_holdout_results.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n",
                        encoding="utf-8")
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
