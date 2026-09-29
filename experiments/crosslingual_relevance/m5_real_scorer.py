"""M5 — real MPNet scorer: gold in first packet via dense + rescue.

Replaces the stub scorer with the real frozen MPNet model (threshold 0.7453).
Tests both Typer (M0 RED target) and M1.5 development tasks.

Expected:
  - M1.5 dev tasks: gold scores above 0.7453 → rescue fires → PASS
  - Typer tasks: gold scores 0.50-0.54 → below threshold → rescue does NOT fire → FAIL
  - This is a legitimate finding: frozen threshold doesn't transfer to Typer

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

# M1.5 development tasks (gold scores above threshold)
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


def _build_vector_service(tmp: Path):
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
        config.retrieval.max_sections_per_source = 20
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


def _check_gold(payload, task) -> dict[str, Any]:
    sources = payload.get("sources", [])
    visible = "\n\n".join(s.get("snippet", "") for s in sources)
    gold_found = any(p in visible for p in task["gold_phrases"])
    budget = docs_context_budget_tokens(payload)
    return {
        "task_id": task["id"],
        "formulation": task["formulation"],
        "project": task["project"],
        "gold_found": gold_found,
        "total_sources": len(sources),
        "budget_tokens": budget,
        "answer_supported": payload.get("answer_supported", False),
        "context_available": payload.get("context_available", False),
    }


def main():
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="m5-real-"))
    print(f"Working directory: {tmp}")
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
    service, config, patcher = _build_vector_service(tmp)
    _index_all(service, roots)
    print("All projects indexed with vectors.\n")

    # Pre-compute MPNet scores for gold blocks to verify threshold applicability
    print("=" * 60)
    print("MPNet score check (gold blocks vs threshold)")
    print("=" * 60)
    for task in TYPER_TASKS + M15_DEV_TASKS:
        docs = documents_for(task["project"], manifest)
        # Find gold passage
        gold_text = ""
        for path, content in docs.items():
            for phrase in task["gold_phrases"]:
                if phrase in content:
                    # Extract the section containing the phrase
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if phrase in line:
                            gold_text = '\n'.join(lines[max(0,i-2):i+10])
                            break
                    if gold_text:
                        break
            if gold_text:
                break
        if gold_text:
            score = mpnet_scorer(task["question"], gold_text)
            above = score >= M2B_THRESHOLD
            print(f"  {task['id']} ({task['formulation']}): score={score:.4f} "
                  f"above_threshold={above} {'✓' if above else '✗'}")
        else:
            print(f"  {task['id']}: gold text not found")

    # Run all tasks with real MPNet scorer
    print(f"\n{'='*60}")
    print("M5 with real MPNet scorer (frozen threshold 0.7453)")
    print(f"{'='*60}")

    results = []
    for task in TYPER_TASKS + M15_DEV_TASKS:
        root = roots[task["project"]]
        request = {"question": task["question"], "project_path": root, "scope": "all"}
        with installed(mpnet_scorer, threshold=M2B_THRESHOLD, question=task["question"]):
            payload, trace = observe_call(service, request)
        r = _check_gold(payload, task)
        results.append(r)
        status = "PASS" if r["gold_found"] else "FAIL"
        print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
              f"gold_found={r['gold_found']} sources={r['total_sources']} "
              f"budget={r['budget_tokens']} context_available={r['context_available']}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    typer_results = [r for r in results if r["project"] == "typer"]
    m15_results = [r for r in results if r["project"] != "typer"]
    typer_pass = sum(1 for r in typer_results if r["gold_found"])
    m15_pass = sum(1 for r in m15_results if r["gold_found"])
    print(f"Typer (M0 target): {typer_pass}/{len(typer_results)}")
    print(f"M1.5 dev: {m15_pass}/{len(m15_results)}")

    # Save
    output = {
        "scorer": model_identity(),
        "threshold": M2B_THRESHOLD,
        "results": results,
        "summary": {
            "typer_pass": typer_pass,
            "typer_total": len(typer_results),
            "m15_pass": m15_pass,
            "m15_total": len(m15_results),
        },
    }
    out_path = Path("experiments/crosslingual_relevance/m5_real_scorer_results.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n",
                        encoding="utf-8")
    print(f"\nResults saved to {out_path}")

    patcher.stop()


if __name__ == "__main__":
    main()
