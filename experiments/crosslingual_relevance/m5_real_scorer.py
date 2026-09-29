"""M5 — real MPNet scorer: gold in first packet via dense + rescue.

Replaces the stub scorer with the real frozen MPNet model (threshold 0.7453).
Tests both Typer (M0 RED target) and M1.5 development tasks.

Scores are recorded on the actual runtime evidence. Neither a manually selected
gold window nor one matching keyword is proof of first-packet completeness.
Historical scores are not predictions for the instrumented replay.

Usage:
    python -m experiments.crosslingual_relevance.m5_real_scorer
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

from experiments.crosslingual_relevance.context_rescue import installed, M2B_THRESHOLD
from experiments.crosslingual_relevance.mpnet_scorer import mpnet_scorer, model_identity

DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DENSE_DIM = 768

# Typer tasks (M0 RED target)
TYPER_TASKS = [
    {
        "id": "typer-mixed-ru", "project": "typer", "formulation": "mixed",
        "question": "Как записать только отрицательное имя boolean option: важен ли пробел перед /?",
        "gold_phrases": ["only *CLI option* names to set the `False` value",
                         "use a space and a single `/` and pass the negative name after"],
    },
    {
        "id": "typer-pure-ru", "project": "typer", "formulation": "RU",
        "question": "Как записать только отрицательное имя логического параметра: важен ли пробел перед косой чертой?",
        "gold_phrases": ["only *CLI option* names to set the `False` value",
                         "use a space and a single `/` and pass the negative name after"],
    },
    {
        "id": "typer-en", "project": "typer", "formulation": "EN",
        "question": "How to declare only the negative name for a boolean option: is the space before / significant?",
        "gold_phrases": ["only *CLI option* names to set the `False` value",
                         "use a space and a single `/` and pass the negative name after"],
    },
]

# Existing M1.5 development tasks; no assumption about real scorer scores
M15_DEV_TASKS = [
    {
        "id": "m15-dev-01", "project": "httpx", "formulation": "mixed",
        "question": "Какое поведение timeout по умолчанию в HTTPX: сколько секунд и какое исключение?",
        "gold_phrases": ["enforces timeouts", "TimeoutException", "5 seconds"],
    },
    {
        "id": "m15-dev-02", "project": "ruff", "formulation": "EN",
        "question": "Does enabling preview automatically enable all preview rules?",
        "gold_phrases": ["preview mode is enabled", "selecting rule categories"],
    },
    {
        "id": "m15-dev-03", "project": "starlette", "formulation": "RU",
        "question": "Когда выполняется teardown lifespan относительно соединений и фоновых задач?",
        "gold_phrases": ["teardown", "lifespan"],
    },
    {
        "id": "m15-dev-04", "project": "pydantic", "formulation": "mixed",
        "question": "Что specifies AliasPath: какой path to a field using aliases?",
        "gold_phrases": ["AliasPath", "path to a field"],
    },
]

ALL_PROJECTS = ["httpx", "ruff", "starlette", "pydantic", "typer"]


def _build_vector_service(tmp: Path, *, max_sections_per_source: int = 20):
    import scripts.run_project_docs_self_host_gate as gate
    from docmancer.core.config import VectorStoreConfig
    from docmancer.core.product_identity import ensure_owned_home

    state = tmp / "vstate"; state.mkdir(parents=True, exist_ok=True)
    home_dir = tmp / "vhome"; home_dir.mkdir(parents=True, exist_ok=True)
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
        config.retrieval.max_sections_per_source = max_sections_per_source
        config.embeddings.provider = "fastembed"
        config.embeddings.model = DENSE_MODEL
        config.embeddings.dimensions = DENSE_DIM
        config.embeddings.sparse_model = None
        config.embeddings.cache = "/tmp/fastembed_cache"
        config.vector_store = VectorStoreConfig(
            provider="sqlite-vec",
            collection=f"m5real_{uuid.uuid4().hex[:8]}",
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


def _index_all(service, roots: dict[str, str]):
    for project, root in roots.items():
        result = service.sync_project_docs(root, with_vectors=True)
        if result.status != 'success':
            raise RuntimeError(f"index failed for {project}: {result.status}")


def _check_gold(payload, task, *, audit_errors=None) -> dict[str, Any]:
    from .evaluation_v2 import assess_packet
    assessment = assess_packet(payload, task, audit_errors=audit_errors)
    return {"task_id":task["id"], "formulation":task["formulation"], "project":task["project"],
        "gold_found":assessment["all_required_facts"] and not assessment["canonical_errors"],
        "total_sources":len(payload.get("sources",[])),
        "budget_tokens":docs_context_budget_tokens(payload),
        "answer_supported":payload.get("answer_supported",False),
        "context_available":payload.get("context_available",False),
        "assessment":assessment}


def _run(max_sections_per_source: int = 20):
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="m5-real-"))
    print(f"Working directory: {tmp}")
    from .mpnet_scorer import _get_model
    _get_model()  # Verify the pinned local model before any indexing/experiment.
    print(f"Model: {model_identity()}")
    print(f"Threshold: {M2B_THRESHOLD}")

    # Load and index all projects
    _, _, manifest = load_protocol()
    roots = {}
    for project in ALL_PROJECTS:
        docs = documents_for(project, manifest)
        root = tmp / "projects" / project
        write_project(root, docs)
        roots[project] = str(root)

    print("Building vector service...")
    service, config, patcher = _build_vector_service(tmp, max_sections_per_source=max_sections_per_source)
    try:
        _index_all(service, roots)
        print("All projects indexed with vectors.\n")

        # No oracle-selected gold window is sent to the scorer. All recorded inputs
        # below come from actual qualification/projection calls, with exact hashes.
        # Run all tasks with real MPNet scorer
        print(f"\n{'='*60}")
        print("M5 with real MPNet scorer (frozen threshold 0.7453)")
        print(f"{'='*60}")

        results = []
        executions = []
        for task in TYPER_TASKS + M15_DEV_TASKS:
            root = roots[task["project"]]
            request = {"question": task["question"], "project_path": root, "scope": "all"}
            from .context_rescue import BoundedScorer
            from eval.evidence_quality_v2.run import audit_payload
            bounded = BoundedScorer(mpnet_scorer, capture_text=True)
            with installed(bounded, threshold=M2B_THRESHOLD, question=task["question"]):
                payload, trace = observe_call(service, request)
            errors = audit_payload(payload, trace["snapshot"], Path(root))
            r = _check_gold(payload, task, audit_errors=errors)
            r["scorer_executed"] = bounded.summary["evaluations"] > 0
            r["scorer_degraded"] = bounded.degraded
            r["scorer_model_verified"] = bounded.identity().get("verified") is True
            r["context_pass_is_not_causal_model_gain"] = True
            executions.append({"request":request,"payload":payload,"trace":trace,
                               "scorer_events":bounded.events,"scorer_summary":bounded.summary})
            results.append(r)
            status = r["assessment"]["verdict"]
            print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
                  f"gold_found={r['gold_found']} sources={r['total_sources']} "
                  f"budget={r['budget_tokens']} context_available={r['context_available']}")

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        typer_results = [r for r in results if r["project"] == "typer"]
        m15_results = [r for r in results if r["project"] != "typer"]
        typer_pass = sum(1 for r in typer_results if r["assessment"]["verdict"] == "PASS")
        m15_pass = sum(1 for r in m15_results if r["assessment"]["verdict"] == "PASS")
        print(f"Typer (M0 target): {typer_pass}/{len(typer_results)}")
        print(f"M1.5 dev: {m15_pass}/{len(m15_results)}")

        # Save
        output = {
            "schema_version":2,
            "evaluation_kind":"real_model_with_canonical_claim_audit",
            "max_sections_per_source":max_sections_per_source,
            "gold_oracle_used":False,
            "scorer": model_identity(),
            "executions":executions,
            "threshold": M2B_THRESHOLD,
            "results": results,
            "summary": {
                "typer_pass": typer_pass,
                "typer_total": len(typer_results),
                "m15_pass": m15_pass,
                "m15_total": len(m15_results),
            },
        }
        from .evaluation_v2 import save_new_report
        out_path = Path("experiments/crosslingual_relevance/review_runs") / f"m5-real-{uuid.uuid4().hex}.json"
        save_new_report(out_path, json.loads(json.dumps(output,default=str)))
        print(f"\nResults saved to {out_path}")
    finally:
        patcher.stop()



def main():
    import argparse
    from .pinned_embedding_session import pinned_embeddings
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-sections-per-source',type=int,choices=(2,20),default=20)
    args=parser.parse_args()
    with pinned_embeddings():
        _run(args.max_sections_per_source)


if __name__ == "__main__":
    main()
