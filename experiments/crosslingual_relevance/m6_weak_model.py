"""M6 — weak model evaluation protocol.

Four conditions on same prompt per holdout task:
  1. No context: question only
  2. Baseline context: lexical baseline (condition A)
  3. New context: dense + rescue (condition D)
  4. Oracle context: verified sufficient packet ≤ 800 tokens

The oracle packet contains the gold passage directly, extracted from source
files. It does NOT give the gold answer — it gives the document passage that
contains the answer, same as a perfect retriever would.

Actual LLM evaluation requires an external small model (e.g., phi-3-mini,
gemma-2b, qwen2.5-1.5b). This script prepares the four context conditions
and saves them as JSON for offline evaluation.

Protocol:
  - Same model, same settings (temperature=0, max_tokens=512, seed=42)
  - Judge does NOT see variant names (blind evaluation)
  - Judge is NOT the tested weak model
  - Metrics: unsupported claims, correct refusals, citation accuracy
  - Per language group, not aggregated

Usage:
    python -m experiments.crosslingual_relevance.m6_weak_model
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.evidence_quality_v2.run import documents_for, load_protocol

from experiments.crosslingual_relevance.m6_holdout import HOLDOUT_TASKS, PROJECTS


def _extract_gold_passage(task: dict, docs: dict[str, str]) -> str:
    """Extract the gold passage text from source docs."""
    content = docs[task["gold_path"]]
    lines = content.split("\n")
    # Use the first gold line range (the one with covered facts)
    gl_start, gl_end = task["gold_lines"][0]
    return "\n".join(lines[gl_start - 1: gl_end])


def _build_oracle_packet(task: dict, docs: dict[str, str]) -> str:
    """Build a verified sufficient oracle packet ≤ 800 tokens."""
    passage = _extract_gold_passage(task, docs)
    # Simple token estimate: ~4 chars per token
    estimated_tokens = len(passage) // 4
    # If passage is too long, truncate to fit 800 tokens
    if estimated_tokens > 750:
        # Leave room for formatting
        max_chars = 750 * 4
        passage = passage[:max_chars].rsplit("\n", 1)[0] + "\n..."
    return f"# Source: {task['gold_path']}\n\n{passage}"


def _build_prompt(question: str, context: str | None) -> str:
    """Build a standard prompt for the weak model."""
    if context is None:
        return (
            f"Answer the following question. If you don't know, say so.\n\n"
            f"Question: {question}\n\nAnswer:"
        )
    return (
        f"Answer the question using only the provided documentation context.\n"
        f"If the context does not contain the answer, say you don't know.\n"
        f"Cite the source path for any claim you make.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )


def main():
    _, _, manifest = load_protocol()
    docs_map = {}
    for project in PROJECTS:
        docs_map.update(documents_for(project, manifest))

    # Load holdout results from condition A and D
    results_path = Path("experiments/crosslingual_relevance/m6_holdout_results.json")
    holdout_results = json.loads(results_path.read_text())

    evaluations = []
    for task in HOLDOUT_TASKS:
        task_id = task["id"]

        # Condition 1: No context
        no_context_prompt = _build_prompt(task["question"], None)

        # Condition 2: Baseline context (from condition A results)
        # We need the actual sources — re-run is not needed, use saved data
        baseline_entry = next(
            (e for e in holdout_results["condition_A_lexical_baseline"] if e["task_id"] == task_id),
            None,
        )

        # Condition 3: New context (from condition D results)
        new_entry = next(
            (e for e in holdout_results["condition_D_dense_rescue"] if e["task_id"] == task_id),
            None,
        )

        # Condition 4: Oracle context
        oracle_context = _build_oracle_packet(task, docs_map)
        oracle_prompt = _build_prompt(task["question"], oracle_context)

        # Get fact description for judging
        fact_desc = ""
        for t in HOLDOUT_TASKS:
            if t["id"] == task_id:
                # Read from manifest
                m = json.loads(Path("experiments/crosslingual_relevance/m15_evaluation_manifest.json").read_text())
                for ht in m["splits"]["holdout"]:
                    if ht["id"] == task_id:
                        for f in ht.get("facts", []):
                            fact_desc = f["description"]
                        break
                break

        evaluations.append({
            "task_id": task_id,
            "formulation": task["formulation"],
            "project": task["project"],
            "question": task["question"],
            "fact_description": fact_desc,
            "gold_phrases": task["gold_phrases"],
            "conditions": {
                "no_context": {
                    "prompt": no_context_prompt,
                    "context": None,
                },
                "baseline_context": {
                    "prompt": "[requires re-running lexical service to capture sources]",
                    "context_sources": baseline_entry["total_sources"] if baseline_entry else None,
                    "gold_in_packet": baseline_entry["gold_in_packet"] if baseline_entry else None,
                },
                "new_context": {
                    "prompt": "[requires re-running dense+rescue service to capture sources]",
                    "context_sources": new_entry["total_sources"] if new_entry else None,
                    "gold_in_packet": new_entry["gold_in_packet"] if new_entry else None,
                    "budget_tokens": new_entry["budget_tokens"] if new_entry else None,
                },
                "oracle_context": {
                    "prompt": oracle_prompt,
                    "context": oracle_context,
                    "gold_phrases_present": all(p in oracle_context for p in task["gold_phrases"]),
                },
            },
            "model_settings": {
                "model": "[to be filled: e.g., phi-3-mini-4k-instruct]",
                "temperature": 0,
                "max_tokens": 512,
                "seed": 42,
                "n_runs": 1,
            },
            "judging_protocol": {
                "judge": "[to be filled: separate model, NOT the tested weak model]",
                "blind": True,
                "criteria": [
                    "unsupported_claims: count of claims not supported by context",
                    "correct_refusals: did model refuse when context lacks answer?",
                    "citation_accuracy: are cited paths correct?",
                    "fact_coverage: does answer contain the verifiable rule?",
                ],
            },
        })

    output = {
        "description": "M6 weak model evaluation protocol. Requires external LLM to execute.",
        "holdout_tasks": len(HOLDOUT_TASKS),
        "conditions": ["no_context", "baseline_context", "new_context", "oracle_context"],
        "evaluations": evaluations,
        "notes": [
            "Baseline is already 4/4 on holdout (no cross-lingual gap in holdout tasks).",
            "One improvement: C→D (dense baseline 3/4 → dense+rescue 4/4, httpx-mixed).",
            "Per plan: 'baseline already full → no proof of improvement by this criterion'.",
            "Original RU/mixed fix proven in M5 (Typer), not in holdout.",
            "Weak model evaluation requires external LLM access.",
        ],
    }

    out_path = Path("experiments/crosslingual_relevance/m6_weak_model_protocol.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Weak model protocol saved to {out_path}")
    print(f"  {len(evaluations)} tasks × 4 conditions = {len(evaluations) * 4} prompts")
    print(f"  Oracle context gold phrases present: "
          f"{sum(1 for e in evaluations if e['conditions']['oracle_context']['gold_phrases_present'])}/{len(evaluations)}")

    # Verify oracle packets ≤ 800 tokens
    for e in evaluations:
        ctx = e["conditions"]["oracle_context"]["context"]
        estimated_tokens = len(ctx) // 4
        print(f"  {e['task_id']}: oracle ~{estimated_tokens} tokens, gold_present={e['conditions']['oracle_context']['gold_phrases_present']}")


if __name__ == "__main__":
    main()
