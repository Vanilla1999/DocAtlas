"""Opt-in semantic evidence audit using a pinned local SQuAD2 QA reader.

A predicted answer span is a hypothesis, NOT a proof of entailment.
Past QA enforcement failed useful-context acceptance. These experimental
modes never set answer_supported, refuse an answer, or read a new source.
"""
from __future__ import annotations
from hashlib import sha256
import os
from pathlib import Path
import re
import time

POLICIES = frozenset({"semantic-audit-v1", "semantic-rescue-v1", "semantic-prune-v1"})
MAX_QA_PROBES = 3
MAX_QA_SECONDS = 45
MIN_PRUNE_PROBES = 2


def _questions(question, tokenizer):
    from .facet_selection import question_probes
    probes, fallback = question_probes(question)
    valid, unscored = [], []
    for probe in probes:
        if len(valid) >= MAX_QA_PROBES:
            unscored.append("probe_budget")
            continue
        if re.search(r"[\u0400-\u04ff]", probe):
            unscored.append("unsupported_query_language")
        elif not (0 < len(tokenizer.encode(probe, add_special_tokens=False).ids) <= 64):
            unscored.append("query_length")
        else:
            valid.append(probe)
    if fallback:
        unscored.append(fallback)
    return valid, unscored


def _span(result):
    candidate = result.get("candidate")
    if result.get("decision") != "candidate_answer" or not candidate:
        return None
    return (candidate.get("identity_sha256"), candidate.get("char_start"),
            candidate.get("char_end"))


def review(question, rows, sections, snapshot, ranking, count, policy):
    """Audit only admitted original rows; rescue and prune are isolated opt-ins.

    Semantic judgments are fallible extractive QA hypotheses, compared to the
    full request-admitted pool, and always recorded as unverified.
    """
    from . import answerability as qa
    from .section_compression import SectionCompressionError
    if policy not in POLICIES:
        raise SectionCompressionError("semantic_sufficiency_invalid_policy")
    started = time.monotonic()
    configured = os.environ.get("DOCATLAS_SUFFICIENCY_MODEL_DIR", "")
    if not configured or not Path(configured).is_absolute():
        raise SectionCompressionError("semantic_sufficiency_model_unavailable")
    directory = Path(configured).resolve()
    if not qa._LOCK.acquire(timeout=MAX_QA_SECONDS):
        raise SectionCompressionError("semantic_sufficiency_resource_limit")
    try:
        if qa._ENGINE is None or qa._ENGINE_PATH != directory:
            qa._ENGINE, qa._ENGINE_PATH = None, None
            qa._ENGINE = qa._Reader(directory)
            qa._ENGINE_PATH = directory
        reader = qa._ENGINE
        probes, unscored = _questions(question, reader.tokenizer)
        chosen = list(ranking[:count])
        original = set(chosen)
        full_contexts = qa._contexts(rows, snapshot)
        observations, suggestions = [], []

        def contexts_for(indices):
            ids = {row["evidence_id"] for i in indices for row in sections[i].rows}
            return qa._contexts([row for row in rows if row["evidence_id"] in ids], snapshot)

        for probe in probes:
            if time.monotonic() - started >= MAX_QA_SECONDS:
                unscored.append("time_budget")
                break
            full = reader.assess(probe, full_contexts)
            current = reader.assess(probe, contexts_for(chosen))
            all_span, chosen_span = _span(full), _span(current)
            gap = bool(all_span and all_span != chosen_span and
                       (chosen_span is None or
                        full["best_span_minus_null"] > current["best_span_minus_null"]))
            if gap and policy == "semantic-rescue-v1":
                ids = set((full.get("candidate") or {}).get("source_ids") or [])
                for index in ranking:
                    if index not in chosen and any(
                        row["evidence_id"] in ids for row in sections[index].rows
                    ):
                        chosen.append(index)
                        suggestions.append(index)
            observations.append({
                "probe_sha256": sha256(probe.encode()).hexdigest(),
                "pool_span_hypothesis": all_span is not None,
                "selected_span_hypothesis": chosen_span is not None,
                "span_agreement": all_span == chosen_span if all_span else None,
                "candidate_gap": gap,
                "pool_margin": round(full["best_span_minus_null"], 3),
                "selected_margin": round(current["best_span_minus_null"], 3),
                "model_pairs": full["pairs"] + current["pairs"],
            })

        # Experimental counterfactual pruning. Never delete when the checker
        # abstained or any query view remained unchecked. Limit candidate
        # removals and require stable original-source answer coordinates.
        if (policy == "semantic-prune-v1" and not unscored
                and len(observations) >= MIN_PRUNE_PROBES
                and all(x["selected_span_hypothesis"] and x["span_agreement"]
                        for x in observations)):
            baselines = [reader.assess(p, contexts_for(chosen))
                         for p in probes[:len(observations)]]
            for index in list(reversed(chosen))[:2]:
                if len(chosen) <= 1 or time.monotonic() - started >= MAX_QA_SECONDS:
                    break
                remaining = [j for j in chosen if j != index]
                contexts = contexts_for(remaining)
                if all(_span(reader.assess(probe, contexts)) == _span(baseline)
                       for probe, baseline in zip(probes, baselines)):
                    chosen = remaining
                    suggestions.append(index)
    except qa.AnswerabilityError as exc:
        raise SectionCompressionError("semantic_sufficiency_" + exc.reason_code) from exc
    finally:
        qa._LOCK.release()

    new_set = set(chosen)
    order = chosen + [i for i in ranking if i not in new_set]
    receipt = {
        "checker": "qa_span_counterfactual_v1",
        "policy": policy, "model_repo": qa.MODEL_REPO,
        "model_revision": reader.manifest["revision"],
        "probes_scored": len(observations), "probes_unscored": unscored,
        "probe_observations": observations,
        "status": ("unknown" if unscored or not observations or
                   any(not x["pool_span_hypothesis"] for x in observations)
                   else "candidate_gap" if any(x["candidate_gap"] for x in observations)
                   else "candidate_spans_agree"),
        "original_selected_groups": len(original),
        "selected_after_check": len(chosen),
        "added_groups": len([i for i in suggestions if i not in original]),
        "removed_groups": len([i for i in suggestions if i in original and i not in new_set]),
        "semantic_sufficiency_certified": False,
        "corpus_absence_proven": False, "answer_supported_changed": False,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    return order, len(chosen), receipt
