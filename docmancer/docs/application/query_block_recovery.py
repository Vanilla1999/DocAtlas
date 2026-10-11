"""Deliver selected inspection context or retain its unissued continuation.

Only authenticated snapshots of already-admitted documents are inspected. This
changes an exploratory draft target, never a requested-part obligation or an
already-registered resource. The public query, citations and proof are retained.
"""
from copy import deepcopy

from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
from .joint_context_candidates import _context_row, _verified_document
from .joint_context_lineage import retained_seed_mapping
from .joint_context_selection import _finish, unread_lines
from .model_visible_projection import (
    _snapshot_entry, docs_context_budget_tokens, validate_model_visible_projection,
)
from .query_block_context import MAX_OPTIONS, ranked_blocks
from .source_continuation import (
    SourceContinuationReader, _read_next_row, attach_docs_context_read_next,
)


def select_query_block_recovery(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int | None):
    plan = retrieval.get("documentation_query_plan") or {}
    root = str(retrieval.get("_source_continuation_project_root") or "")
    previous = payload.get("read_next") or []
    if (not root or payload.get("kind") != "docs_context"
        or payload.get("support_status") not in {"retrieval_only", "insufficient_evidence"}
        or any(payload.get(k) is not False for k in ("answer_supported", "answer_available", "edit_ready"))
        or (payload.get("context_quality") or {}).get("status") == "checked"
        or len(previous) > 1
        or previous and previous[0].get("reason") != "inspect_source_context"
        or any(q.get("origin") == "host_lookup" for q in plan.get("queries", []) if isinstance(q, dict))):
        return payload, snapshot
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    budget = max_tokens
    proposals, seen = [], set()
    seeds = [(seed, (snapshot.get(seed["evidence_id"]) or {}).get("source"))
             for seed in payload.get("sources", [])]
    max_documents = 3  # prior optional scan work, not packet source eligibility
    if not seeds:
        from .inspection_recovery_seeds import inspection_recovery_seeds
        seeds = inspection_recovery_seeds(retrieval)
        max_documents = 32  # unchanged bounded inspection-seed acquisition
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
        if len(seen) >= max_documents:
            break
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
                    continue
                bindings["__read_next__"] = {"source": deepcopy(candidate)}
                if validate_model_visible_projection(trial, snapshot=bindings, max_tokens=budget):
                    continue
                fully_unread = unseen == [(row["line_start"], row["line_end"])]
                proposals.append((rank, start, trial, bindings, row, candidate, fully_unread))
    if not proposals:
        return payload, snapshot
    best = min(proposals, key=lambda c: (-c[0][0], -c[0][1], c[1]))
    _, _, result, bindings, row, candidate, fully_unread = best
    kind = "unissued_inspection_only"
    if payload.get("sources") and payload.get("support_status") == "retrieval_only" and fully_unread:
        # The selected range already passed source, owner and policy checks.
        # Deliver its exact loaded bytes as supplementary context; never expand
        # a partially visible range or turn an empty result into admitted facts.
        draft, draft_bindings = deepcopy(result), deepcopy(bindings)
        draft["sources"].append(deepcopy(row))
        draft_bindings[row["evidence_id"]] = _snapshot_entry(candidate, row)
        finished = _finish(draft, draft_bindings, retrieval, root, budget)
        if finished is not None:
            p, b, r = finished
            # Include the new range in retention: removing its continuation is
            # valid only if these same canonical bytes actually survive.
            mapping = retained_seed_mapping(draft, draft_bindings, p, b)
            surviving = {source["evidence_id"]: source for source in p["sources"]}
            if (mapping and not p.get("read_next")
                and p.get("covered_query_ids") == result.get("covered_query_ids")
                and not any(old.get("source_uri")
                    and surviving[mapping[old["evidence_id"]]].get("source_uri") != old["source_uri"]
                    for old in result["sources"])
                and not validate_model_visible_projection(p, snapshot=b, max_tokens=budget)):
                result, bindings = p, b
                retrieval.clear()
                retrieval.update(r)
                kind = "materialized_inspection"
    retrieval.setdefault("retrieval_diagnostics", {}).setdefault("docs_context_projection", {})["block_recovery"] = {
        "kind": kind, "eligible_ranges": len(proposals),
        "budget_tokens": docs_context_budget_tokens(result),
    }
    return result, bindings
