"""Choose a useful unissued inspection range, without crediting unread facts.

Only authenticated snapshots of already-admitted documents are inspected. This
changes an exploratory draft target, never a requested-part obligation or an
already-registered resource. The public query, citations and proof are retained.
"""
from copy import deepcopy

from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
from .joint_context_candidates import _context_row, _verified_document
from .joint_context_selection import unread_lines
from .model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS, INSUFFICIENT_EVIDENCE_MAX_TOKENS,
    docs_context_budget_tokens, validate_model_visible_projection,
)
from .query_block_context import MAX_OPTIONS, ranked_blocks
from .source_continuation import (
    SourceContinuationReader, _read_next_row, attach_docs_context_read_next,
)


def select_query_block_recovery(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int):
    plan = retrieval.get("documentation_query_plan") or {}
    root = str(retrieval.get("_source_continuation_project_root") or "")
    previous = payload.get("read_next") or []
    if (not root or payload.get("kind") != "docs_context"
        or payload.get("support_status") not in {"retrieval_only", "insufficient_evidence"}
        or any(payload.get(k) is not False for k in ("answer_supported", "answer_available", "edit_ready"))
        or (payload.get("context_quality") or {}).get("status") == "checked"
        or len(payload.get("sources", [])) > 3
        or len(previous) > 1
        or previous and previous[0].get("reason") != "inspect_source_context"
        or any(q.get("origin") == "host_lookup" for q in plan.get("queries", []) if isinstance(q, dict))):
        return payload, snapshot
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    budget = min(max_tokens, DOCS_CONTEXT_MAX_TOKENS)
    proposals, seen = [], set()
    seeds = [(seed, (snapshot.get(seed["evidence_id"]) or {}).get("source"))
             for seed in payload.get("sources", [])]
    if not seeds:
        from .inspection_recovery_seeds import inspection_recovery_seeds
        seeds = inspection_recovery_seeds(retrieval)
        budget = min(budget, INSUFFICIENT_EVIDENCE_MAX_TOKENS)
    for seed, source in seeds:
        if not isinstance(source, dict):
            continue
        raw = _verified_document(source, seed)
        if raw is None:
            continue
        ref = source["_reference_evidence"]
        key = (seed["project_identity"], seed["path_or_url"], ref["source"]["content_sha256"])
        if key in seen:
            continue
        seen.add(key)
        ranked = ranked_blocks(raw, ref["source"]["document_id"], question)
        old_rank = (-1, -1.0)
        if previous:
            old = previous[0]
            if old.get("path") != seed["path_or_url"]:
                continue  # scores from different document-local BM25 pools are not comparable
            for rank, a, z, _ in ranked:
                first, last = raw.count("\n", 0, a) + 1, raw.count("\n", 0, z - 1) + 1
                if first <= old["line_end"] and old["line_start"] <= last:
                    old_rank = max(old_rank, rank)
        visible = [(row["line_start"], row["line_end"]) for row in payload.get("sources", [])
                   if row["path_or_url"] == seed["path_or_url"] and row["project_identity"] == seed["project_identity"]]
        for rank, a, z, owner in ranked[:MAX_OPTIONS]:
            if rank <= old_rank:
                continue
            # A read target is bounded inspection of the relevant block and
            # its contiguous section tail, not another isolated clipped sentence.
            # Recheck policies on the whole range; never jump to a sibling owner.
            lines = raw[a:owner.char_end].splitlines(keepends=True)
            extended = min(owner.char_end, a + sum(map(len, lines[:SourceContinuationReader.max_lines])))
            proposal = _context_row(source, seed, raw, owner, a, extended, supplementary=True)
            if proposal is None:
                proposal = _context_row(source, seed, raw, owner, a, z, supplementary=True)
            if proposal is None:
                continue
            row, candidate = proposal
            required = {r["mention"]["mention_id"] for r in
                        (source.get("_reference_root_plan") or {}).get("references", [])
                        if r.get("role") == "semantic_subject"}
            probe, reason = prepare_reference_probe({}, candidate=candidate, evidence_text=row["snippet"])
            bound = {r["mention_id"] for r in probe.get("reference_bindings", []) if r.get("role") == "semantic_subject"}
            if reason is not None or not required <= bound:
                continue
            unseen = unread_lines(row["line_start"], row["line_end"], visible)
            for start, end in unseen[:1]:
                if end - start + 1 > SourceContinuationReader.max_lines:
                    continue
                target = _read_next_row(root, candidate, line_start=start, line_end=end,
                                        reason="inspect_source_context")
                if target is None:
                    continue
                trial, bindings = deepcopy(payload), deepcopy(snapshot)
                if not attach_docs_context_read_next(trial, target, max_tokens=budget):
                    from .context_packet_labels import compact_section_labels
                    trial, bindings = compact_section_labels(payload, snapshot)
                    if not attach_docs_context_read_next(trial, target, max_tokens=budget):
                        # These locators have not been issued. Replace only
                        # redundant same-snapshot exploratory readers with the
                        # explicit bounded inspection target, never obligations
                        # or capabilities already stored in the reader registry.
                        for public in trial.get("sources", []):
                            old_bound = bindings.get(public.get("evidence_id")) or {}
                            old_source = old_bound.get("source") or {}
                            if (public.get("path_or_url") == target["path"]
                                and public.get("project_identity") == target["project_identity"]
                                and old_source.get("_source_snapshot_sha256") == target["snapshot_sha256"]):
                                public.pop("source_uri", None)
                                old_bound.pop("source_uri", None)
                                (old_bound.get("projected_source") or {}).pop("source_uri", None)
                        if not attach_docs_context_read_next(trial, target, max_tokens=budget):
                            continue
                bindings["__read_next__"] = {"source": deepcopy(candidate)}
                if validate_model_visible_projection(trial, snapshot=bindings, max_tokens=budget):
                    continue
                proposals.append((rank, start, trial, bindings))
    if not proposals:
        return payload, snapshot
    best = min(proposals, key=lambda c: (-c[0][0], -c[0][1], c[1]))
    _, _, result, bindings = best
    retrieval.setdefault("retrieval_diagnostics", {}).setdefault("docs_context_projection", {})["block_recovery"] = {
        "kind": "unissued_inspection_only", "eligible_ranges": len(proposals),
        "budget_tokens": docs_context_budget_tokens(result),
    }
    return result, bindings
