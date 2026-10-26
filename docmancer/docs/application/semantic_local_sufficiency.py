"""Local evidence audits, with unknown/no-complete-scan always non-destructive.

QA-span agreement is not sufficiency. NLI preservation is separately evaluated
and never grants answer authority or proves absence in the document corpus.
"""
from __future__ import annotations
from hashlib import sha256
import os
from pathlib import Path
import re
import time

POLICIES = frozenset({"semantic-audit-v1", "semantic-rescue-v1", "semantic-prune-v1",
                      "semantic-exact-prune-v1", "semantic-nli-prune-v1"})
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
        elif re.search(r"[\u0400-\u04ff]", probe):
            unscored.append("unsupported_query_language")
        elif not 0 < len(tokenizer.encode(probe, add_special_tokens=False).ids) <= 64:
            unscored.append("query_length")
        else:
            valid.append(probe)
    if fallback:
        unscored.append(fallback)
    return valid, unscored


def _span(result):
    c = result.get("candidate")
    return (c["identity_sha256"], c["char_start"], c["char_end"]) if c and result["decision"] == "candidate_answer" else None


def review(question, rows, sections, snapshot, ranking, count, policy):
    from . import answerability as qa
    from .section_compression import SectionCompressionError
    from .semantic_budget import Budget, CachedQA, Exhausted
    if policy in {"semantic-exact-prune-v1", "semantic-nli-prune-v1"}:
        from .semantic_preservation import review as preserve
        return preserve(question, rows, sections, snapshot, ranking, count, policy)
    if policy not in POLICIES:
        raise SectionCompressionError("semantic_sufficiency_invalid_policy")
    budget = Budget(MAX_QA_SECONDS, qa.MAX_PAIRS)
    configured = os.environ.get("DOCATLAS_SUFFICIENCY_MODEL_DIR", "")
    if not configured or not Path(configured).is_absolute():
        raise SectionCompressionError("semantic_sufficiency_model_unavailable")
    directory = Path(configured).resolve()
    if not qa._LOCK.acquire(timeout=MAX_QA_SECONDS):
        raise SectionCompressionError("semantic_sufficiency_resource_limit")
    chosen = list(ranking[:count]); original = list(chosen)
    observations, proposals, unscored = [], [], []
    reader = None; baselines = []
    try:
        if qa._ENGINE is None or qa._ENGINE_PATH != directory:
            qa._ENGINE, qa._ENGINE_PATH = None, None
            qa._ENGINE = qa._Reader(directory)
            qa._ENGINE_PATH = directory
        reader = qa._ENGINE
        probes, unscored = _questions(question, reader.tokenizer)
        def contexts(indices):
            ids = {r["evidence_id"] for i in indices for r in sections[i].rows}
            return qa._contexts([r for r in rows if r["evidence_id"] in ids], snapshot)
        # An incomplete plan cannot authorize any change. Do not pay for
        # guaranteed-unused inference in action modes. Audit may still observe.
        if not unscored or policy == "semantic-audit-v1":
            checker = CachedQA(reader, budget)
            full_contexts, selected_contexts = qa._contexts(rows, snapshot), contexts(chosen)
            for probe in probes:
                budget.check()
                full = checker.assess(probe, full_contexts)
                current = checker.assess(probe, selected_contexts)
                baselines.append(current)
                a, b = _span(full), _span(current)
                gap = bool(a and a != b and (b is None or full["best_span_minus_null"] > current["best_span_minus_null"]))
                observations.append({"probe_sha256": sha256(probe.encode()).hexdigest(),
                    "pool_span_hypothesis": a is not None, "selected_span_hypothesis": b is not None,
                    "span_agreement": a == b if a else None, "candidate_gap": gap})
                if gap:
                    ids = set(full["candidate"]["source_ids"])
                    proposals.extend(i for i in ranking if i not in chosen and
                                     any(r["evidence_id"] in ids for r in sections[i].rows))
            complete = (not unscored and len(observations) == len(probes) and bool(observations)
                        and all(x["pool_span_hypothesis"] for x in observations))
            if complete and policy == "semantic-rescue-v1":
                chosen.extend(i for i in dict.fromkeys(proposals) if i not in chosen)
            if (complete and policy == "semantic-prune-v1" and len(probes) >= MIN_PRUNE_PROBES
                    and all(x["selected_span_hypothesis"] and x["span_agreement"] for x in observations)):
                for index in list(reversed(chosen))[:2]:
                    if len(chosen) <= 1:
                        break
                    trial = [i for i in chosen if i != index]
                    if all(_span(checker.assess(p, contexts(trial))) == _span(b)
                           for p, b in zip(probes, baselines, strict=True)):
                        chosen = trial
    except Exhausted:
        unscored.append("request_budget")
        chosen = original  # atomic rollback: no partial-scan mutations survive
    except qa.AnswerabilityError as exc:
        raise SectionCompressionError("semantic_sufficiency_" + exc.reason_code) from exc
    finally:
        qa._LOCK.release()
    unknown = bool(unscored or not observations or any(not x["pool_span_hypothesis"] for x in observations))
    if unknown:
        chosen = original
    selected = set(chosen)
    receipt = {"checker": "qa_shared_budget_v2", "policy": policy,
        "model_repo": qa.MODEL_REPO, "model_revision": reader.manifest["revision"],
        "probes_scored": len(observations), "probes_unscored": unscored,
        "probe_observations": observations,
        "status": "unknown" if unknown else "candidate_gap" if any(x["candidate_gap"] for x in observations) else "candidate_spans_agree",
        "original_selected_groups": len(original), "selected_after_check": len(chosen),
        "added_groups": len(selected - set(original)), "removed_groups": len(set(original) - selected),
        "proposal_groups": sorted(set(proposals)), "unknown_preserved_selection": unknown and chosen == original,
        "model_pairs": budget.pairs, "model_pair_tokens": budget.pair_tokens, "cache_hits": budget.cache_hits,
        "semantic_sufficiency_certified": False, "corpus_absence_proven": False,
        "answer_supported_changed": False, "runtime_seconds": round(budget.elapsed(), 3)}
    return chosen + [i for i in ranking if i not in selected], len(chosen), receipt
