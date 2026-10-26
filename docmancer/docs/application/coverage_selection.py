"""Experimental local selectors for an already admitted source pool.

Literal query probes are retrieval views, NOT a complete semantic decomposition.
Cross-encoder scores are ranking signals, NOT probabilities or sufficiency proof.
No gold labels, document-specific rules, external calls or new source reads.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import os
import re
import time

POLICIES = frozenset({"mmr-budget-v1", "facet-cover-v1", "facet-guarded-v1",
                      "facet-cover-v2", "facet-guarded-v2", "facet-bundled-v1",
                      "facet-bundled-cover-v1"})
MAX_PROBES = 16
MMR_RELEVANCE = 0.7  # Frozen experiment parameter, not a confidence threshold.


def literal_probes(question: str) -> list[str]:
    """Keep the full question and exact clause/list slices outside code/quotes.

    The full question always remains a probe, including conditions and negation.
    Unsupported languages still get punctuation views; no translation is invented.
    The limit fails explicitly instead of silently dropping a list's tail.
    """
    from .section_compression import SectionCompressionError
    protected = re.compile(r'`[^`]*`|"[^"\n]*"|\([^)]*\)|\[[^]]*\]')
    masked = list(question)
    for match in protected.finditer(question):
        masked[match.start():match.end()] = "_" * len(match.group())
    boundaries = list(re.finditer(r"[,;:?！!？\n]+|\.(?=\s+[A-ZА-Я])|\s+(?:and|or|и|или)\s+",
                                  "".join(masked), flags=re.IGNORECASE))
    parts, start = [question], 0
    for match in boundaries:
        part = question[start:match.start()].strip()
        if part and len(re.findall(r"\w+", part)) >= 1 and len(part) >= 5:
            parts.append(part)
        start = match.end()
    part = question[start:].strip().rstrip(".?!")
    if part and len(part) >= 5:
        parts.append(part)
    # One uninterrupted question does not need a second almost identical view.
    if not boundaries:
        return [question]
    unique, seen = [], set()
    for part in parts:
        key = part.strip().rstrip(".?!").casefold()
        if key not in seen:
            unique.append(part)
            seen.add(key)
    if len(unique) > MAX_PROBES:
        raise SectionCompressionError("section_compression_probe_limit")
    return unique


def contextual_probes(question, tokenizer):
    """Preserve the original subject when scoring a literal follow-up clause.

    Uses only original query text, not gold, source facts or model-generated
    claims. Overlength derived views explicitly fall back to the unchanged
    whole question; no token slice or silent source/query truncation occurs.
    """
    parts = literal_probes(question)
    masked = list(question)
    for m in re.finditer(r'`[^`]*`|"[^"\n]*"|\([^)]*\)|\[[^]]*\]', question):
        masked[m.start():m.end()] = "_" * len(m.group())
    stop = re.search(r"[.!?:;\n]", "".join(masked))
    anchor = question[:stop.end()] if stop else question
    result, fallback = [question], []
    for index, part in enumerate(parts[1:], 1):
        view = anchor if part.strip().rstrip(".?!:;") == anchor.strip().rstrip(".?!:;") else anchor + "\n" + part
        if len(tokenizer.encode(view, add_special_tokens=False).ids) > 128:
            fallback.append(index)
            view = question
        if view not in result:
            result.append(view)
    return result, fallback


def bundle_short_sources(sections, tokenizer):
    """Treat a short native document as one indivisible acquired evidence unit.

    The 512-token bound is the scorer's standard input scale, not a top-k or
    sufficiency threshold. Long documents stay unchanged. Only acquired text
    is joined; unacquired gaps and neighbors are never read or filled.
    """
    from .section_compression import _Section
    groups = {}
    for section in sections:
        groups.setdefault((section.key[0], *section.key[2:]), []).append(section)
    result, bundled, bundled_keys = [], [], set()
    for identity, members in sorted(groups.items()):
        members.sort(key=lambda s: (min(r.get("line_start") or 0 for r in s.rows), s.key))
        text = "\n\n".join(s.text for s in members)
        if len(members) > 1 and len(tokenizer.encode(text, add_special_tokens=False).ids) <= 512:
            rows, ids = [], set()
            for section in members:
                for row in section.rows:
                    if row["evidence_id"] not in ids:
                        rows.append(row)
                        ids.add(row["evidence_id"])
            result.append(_Section((members[0].key[0], "", *members[0].key[2:]), rows, text))
            bundled_keys.add(result[-1].key)
            bundled.append({"path": identity[0], "acquired_sections": len(members)})
        else:
            result.extend(members)
    ordered = sorted(result, key=lambda s: s.key)
    return ordered, bundled, frozenset(i for i, s in enumerate(ordered) if s.key in bundled_keys)


def _tokens(section) -> int:
    from .projection_tokenizer import projection_token_count
    # Estimate the delivered rows, not only the shorter MaxP scoring string.
    visible = [{"path": r.get("path_or_url"), "section": r.get("section"),
                "lines": [r.get("line_start"), r.get("line_end")], "text": r["snippet"]}
               for r in section.rows]
    return max(1, projection_token_count(json.dumps(visible, ensure_ascii=False).encode()))


def _plan(policy, sections, columns, costs, bundled_indices=frozenset()):
    from .section_compression import _adaptive_cutoff
    scores = columns[0]
    root_order = sorted(range(len(sections)), key=lambda i: (-scores[i], sections[i].key))
    count, gap = _adaptive_cutoff([scores[i] for i in root_order], buffer=1)
    if policy == "mmr-budget-v1":
        # Same estimated source-token allowance as B1, but choose by marginal
        # relevance/diversity rather than a prefix. This is a comparator only.
        allowance = sum(costs[i] for i in root_order[:count])
        words = [set(re.findall(r"\w+", s.text.casefold())) for s in sections]
        width = max(scores) - min(scores)
        relevance = [(s - min(scores)) / width if width else 1.0 for s in scores]
        chosen, remaining, spent = [], set(root_order), 0
        while remaining:
            affordable = [i for i in remaining if costs[i] + spent <= allowance]
            if not affordable:
                break
            def utility(i):
                duplicate = max((len(words[i] & words[j]) / max(1, len(words[i] | words[j]))
                                 for j in chosen), default=0.0)
                return (-(MMR_RELEVANCE * relevance[i] - (1 - MMR_RELEVANCE) * duplicate),
                        costs[i], sections[i].key)
            best = min(affordable, key=utility)
            chosen.append(best)
            remaining.remove(best)
            spent += costs[best]
        return chosen or root_order[:1], {"source_token_allowance": allowance, "root_gap": gap}
    # Cover every probe's *best observed ranking score*. Exact ties may be
    # satisfied by the same source, with token cost only breaking quality ties.
    # This certifies a ranking objective, never semantic answer coverage.
    winners = [{i for i, score in enumerate(column) if score == max(column)} for column in columns]
    uncovered = set(range(len(columns)))
    chosen = []
    while uncovered:
        options = set.union(*(winners[p] for p in uncovered)) - set(chosen)
        best = min(options, key=lambda i: (
            -sum(i in winners[p] for p in uncovered), costs[i], -scores[i], sections[i].key))
        chosen.append(best)
        uncovered = {p for p in uncovered if best not in winners[p]}
    protected = list(chosen)
    structural_cover = policy == "facet-bundled-cover-v1" and all(i in bundled_indices for i in chosen)
    if (policy in {"facet-guarded-v1", "facet-guarded-v2", "facet-bundled-v1"}
            or (policy == "facet-bundled-cover-v1" and not structural_cover)):
        # Keep the complete B1 proposal as a safety reference, not fixed five.
        # Facet winners are delivered first if the full-packet budget is tight.
        chosen.extend(i for i in root_order[:count] if i not in chosen)
    return chosen, {"structural_probe_cover_only": structural_cover, "probe_winners": [sorted(w) for w in winners],
                    "protected_probe_sections": protected, "root_gap": gap,
                    "root_requested_sections": count}


def select_coverage_sections(payload, snapshot, retrieval, question, policy):
    """Called after the normal enablement, scope and hard-stop guards."""
    from . import section_compression as core
    from .experimental_context_finalization import _rebuild, _refresh_estimate
    rows = payload["sources"]
    sections = core._sections(rows, snapshot)
    configured = os.environ.get("DOCATLAS_MINILM_MODEL_DIR", "")
    if not configured or not Path(configured).is_absolute():
        raise core.SectionCompressionError("section_compression_model_unavailable")
    directory = Path(configured).resolve()
    probes = [question] if policy == "mmr-budget-v1" else literal_probes(question)
    columns, receipts = [], []
    probe_fallbacks, bundles, bundle_indices = [], [], frozenset()
    started = time.monotonic()
    with core._LOCK:
        if core._ENGINE is None or core._ENGINE_PATH != directory:
            core._ENGINE, core._ENGINE_PATH = None, None
            core._ENGINE = core._MiniLM(directory)
            core._ENGINE_PATH = directory
        if policy in {"facet-cover-v2", "facet-guarded-v2", "facet-bundled-v1", "facet-bundled-cover-v1"}:
            probes, probe_fallbacks = contextual_probes(question, core._ENGINE.tokenizer)
        if policy in {"facet-bundled-v1", "facet-bundled-cover-v1"}:
            sections, bundles, bundle_indices = bundle_short_sources(sections, core._ENGINE.tokenizer)
        # One common resource allowance for the ENTIRE request, not per probe.
        for probe in probes:
            remaining_pairs = core.MAX_PAIRS - sum(r["forward_passes"] for r in receipts)
            remaining_seconds = core.MAX_SECONDS - (time.monotonic() - started)
            if remaining_pairs <= 0 or remaining_seconds <= 0:
                raise core.SectionCompressionError("section_compression_resource_limit")
            values, receipt = core._ENGINE.score(
                probe, sections, max_pairs=remaining_pairs, max_seconds=remaining_seconds)
            columns.append(values)
            receipts.append(receipt)
    costs = [_tokens(section) for section in sections]
    order, selection = _plan(policy, sections, columns, costs, bundle_indices)
    requested = len(order)

    def project(indices):
        selected_ids = {r["evidence_id"] for i in indices for r in sections[i].rows}
        retained = [r for r in rows if r["evidence_id"] in selected_ids]
        limited = len(indices) < requested
        result, bindings = _rebuild(payload, snapshot, retrieval, retained,
            reason="budget_limited" if limited else "section_selection")
        if limited:
            result["status"] = "truncated"
            result["source_selection"] = {"candidate_rows": len(rows), "selected_rows": len(retained),
                "omitted_rows": len(rows) - len(retained), "scope": "admitted_candidates", "budget_limited": True}
            _refresh_estimate(result)
        identity = lambda r: tuple(r.get(k) for k in ("evidence_id", "path_or_url", "section", "line_start", "line_end", "snippet"))
        if [identity(r) for r in result["sources"]] != [identity(r) for r in retained]:
            raise core.SectionCompressionError("section_compression_identity_mismatch")
        core.encode_sections(result)  # Exact negotiated complete-packet budget.
        return result, bindings, retained

    selected = list(order)
    while selected:
        try:
            result, bindings, retained = project(selected)
            break
        except core.SectionCompressionError as exc:
            if exc.reason_code != "section_compression_output_limit":
                raise
            selected.pop()
    else:
        raise core.SectionCompressionError("section_compression_output_limit")
    selected_set = set(selected)
    probe_best_retained = [max(column[i] for i in selected) == max(column) for column in columns]
    receipt = {"method": core.MODE, "model_revision": core.MODEL_REVISION,
        "selection_policy": policy, "configured_top_k": None,
        "units": core.selection_units(), "scoring_question_sha256": hashlib.sha256(question.encode()).hexdigest(),
        "candidate_rows": len(rows), "candidate_sections": len(sections),
        "selected_rows": len(retained), "selected_sections": len(selected), "top_k": len(selected),
        "selected_evidence_ids": [r["evidence_id"] for r in retained],
        "forward_passes": sum(r["forward_passes"] for r in receipts),
        "input_pair_tokens": sum(r["input_pair_tokens"] for r in receipts),
        "truncated_tokens": 0, "scoring_seconds": sum(r["scoring_seconds"] for r in receipts),
        "selection_diagnostics": {**selection, "probe_count": len(probes),
            "contextual_probe_fallbacks": probe_fallbacks, "short_source_bundles": bundles,
            "probe_sha256": [hashlib.sha256(p.encode()).hexdigest() for p in probes],
            "ranking_targets_retained": probe_best_retained, "semantic_sufficiency_certified": False,
            "requested_sections": requested, "selected_after_budget": len(selected),
            "budget_limited": len(selected) < requested, "budget_limit_tokens": core.OUTPUT_LIMIT}}
    retrieval.setdefault("retrieval_diagnostics", {})["section_compression"] = deepcopy(receipt)
    observed = core._OBSERVER.get()
    if observed is not None:
        detail = deepcopy(receipt)
        ranking = sorted(range(len(sections)), key=lambda i: (-columns[0][i], sections[i].key))
        detail["ranked_sections"] = [{"rank": rank, "score": columns[0][i],
            "probe_scores": [c[i] for c in columns], "selected": i in selected_set,
            "estimated_visible_tokens": costs[i], "path": sections[i].rows[0].get("path_or_url"),
            "section": sections[i].rows[0].get("section"),
            "scoring_text_sha256": hashlib.sha256(sections[i].text.encode()).hexdigest(),
            "evidence_ids": [r["evidence_id"] for r in sections[i].rows]}
            for rank, i in enumerate(ranking, 1)]
        observed.append(detail)
    return result, bindings
