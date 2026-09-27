"""Experimental pre-publication packet alternatives, never additional retrieval."""
from __future__ import annotations

from copy import deepcopy
from itertools import product, combinations

from .joint_context_candidates import source_options
from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
from .joint_context_lineage import retained_seed_mapping
from .model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS, MAX_DOCS_SOURCES, _refresh_estimate, _snapshot_entry,
    docs_context_budget_tokens, validate_model_visible_projection,
)
from .source_continuation import (
    prepare_docs_context_read_next, attach_docs_context_read_next,
    attach_source_continuation_locators, _read_next_row,
)
from .context_selection import attributable_query_ids, merge_query_matches


def unread_lines(start: int, end: int, visible: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Inclusive interval difference; a later quote never hides a gap."""
    if type(start) is not int or type(end) is not int or not 1 <= start <= end:
        raise ValueError("invalid line interval")
    cursor = start
    out = []
    for a, b in sorted(visible):
        if type(a) is not int or type(b) is not int or not 1 <= a <= b:
            raise ValueError("invalid visible interval")
        if b < cursor or a > end:
            continue
        if a > cursor:
            out.append((cursor, a - 1))
        cursor = max(cursor, b + 1)
        if cursor > end:
            break
    if cursor <= end:
        out.append((cursor, end))
    return out


def _finish(payload: dict, snapshot: dict, retrieval: dict, root: str, budget: int):
    # Ordinary quality/capability primitives on private clones. The real handler
    # registers only the winning DTO, not these candidate drafts.
    from .docs_context_projection import _finalize_quality, _strip_legacy_locators
    p, b, r = deepcopy(payload), deepcopy(snapshot), deepcopy(retrieval)
    p["read_next"] = []
    b.pop("__read_next__", None)
    _strip_legacy_locators(p, b)
    _finalize_quality(r, p, b)
    if docs_context_budget_tokens(p) > budget:
        from .context_packet_labels import compact_section_labels
        p, b = compact_section_labels(p, b)
    if root:
        previous = payload.get("read_next") or []
        if previous:
            target = deepcopy(previous[0])
            source = (snapshot.get("__read_next__") or {}).get("source")
            if not isinstance(source, dict):
                return None
        else:
            target, source = prepare_docs_context_read_next(p, b, r, root=root)
        if target is not None and source is not None:
            visible = [(row["line_start"], row["line_end"]) for row in p["sources"]
                if row["path_or_url"] == target["path"]
                and row["project_identity"] == target["project_identity"]
                and (b[row["evidence_id"]]["source"].get("_source_snapshot_sha256") == target["snapshot_sha256"])]
            remaining = unread_lines(target["line_start"], target["line_end"], visible)
            if remaining:
                a, z = remaining[0]
                target = _read_next_row(root, source, line_start=a, line_end=z, reason=target["reason"])
            else:
                target = None
            if target is not None:
                if attach_docs_context_read_next(p, target, max_tokens=budget):
                    b["__read_next__"] = {"source": deepcopy(source)}
                elif previous:
                    # Unread obligations are not deleted to make a trial fit.
                    return None
        attach_source_continuation_locators(p, b, root=root, max_tokens=budget)
    _refresh_estimate(p)
    return p, b, r


def _draft_subsets(payload: dict, snapshot: dict, trial: dict, bindings: dict, retrieval: dict):
    """Coalesce only draft citations with full canonical lineage and no facet IDs."""
    yield trial, bindings
    if payload.get("facets") or len(trial["sources"]) < 2:
        return
    from .docs_context_projection import _requalify_visible_source
    plan = retrieval.get("documentation_query_plan") or {}
    texts = {str(q.get("query_id") or ""): str(q.get("text") or "")
             for q in plan.get("queries") or () if isinstance(q, dict)}
    for n in range(1, len(trial["sources"])):
        for rows in combinations(trial["sources"], n):
            p = deepcopy(trial)
            p["sources"] = list(deepcopy(rows))
            mapping = retained_seed_mapping(payload, snapshot, p, bindings)
            if not mapping:
                continue
            b = deepcopy(bindings)
            qualified_rows = []
            policy_rejected = False
            for row in p["sources"]:
                original = b[row["evidence_id"]]["source"]
                # Re-run the existing qualifier for the probes attached to
                # every retained occurrence. Never copy its old qualified flag.
                inherited = [original]
                inherited.extend(snapshot[eid]["source"] for eid, covering in mapping.items()
                                 if covering == row["evidence_id"] and eid != row["evidence_id"])
                checked = []
                for origin in inherited:
                    if any(evidence_policy_rejection_reason(
                        probe, visible_text=row["snippet"],
                        catalog_role=str(original.get("catalog_role") or ""), candidate=original,
                        expected_project_identity=row["project_identity"],
                        lifecycle_intent=original.get("_lifecycle_intent", "current"),
                    ) for probe in (origin.get("retrieval_query_matches") or {}).values() if isinstance(probe, dict)):
                        policy_rejected = True
                        break
                    visible = _requalify_visible_source({
                        **original, **row, "_qualification_candidate": original,
                        "_expected_project_identity": row["project_identity"],
                        "retrieval_query_matches": origin.get("retrieval_query_matches") or {},
                    }, query_text=texts)
                    checked.append(visible["retrieval_query_matches"])
                if policy_rejected:
                    break
                matches = merge_query_matches(*checked)
                original = {**original, "retrieval_query_matches": matches,
                    "retrieval_query_ids": [key for key, value in matches.items() if value.get("qualified") is True]}
                visible = {**visible, "retrieval_query_matches": matches,
                           "retrieval_query_ids": original["retrieval_query_ids"]}
                b[row["evidence_id"]] = _snapshot_entry(original, row)
                qualified_rows.append(visible)
            if policy_rejected or not set(payload.get("covered_query_ids") or ()) <= attributable_query_ids(qualified_rows):
                continue
            yield p, b


def packet_alternatives(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int):
    """Yield fully validated bounded candidates; no labels, no URI registration."""
    if (payload.get("kind") != "docs_context" or payload.get("support_status") != "retrieval_only"
        or any(payload.get(k) is not False for k in ("answer_supported", "answer_available", "edit_ready"))
        or (payload.get("context_quality") or {}).get("status") == "checked"
        or not 0 < len(payload.get("sources", [])) <= MAX_DOCS_SOURCES):
        return
    budget = min(max_tokens, DOCS_CONTEXT_MAX_TOKENS)
    groups, intros = [], {}
    for row in payload["sources"]:
        original = (snapshot.get(row["evidence_id"]) or {}).get("source")
        if not isinstance(original, dict):
            return
        options, intro = source_options(row, original)
        groups.append(options)
        if intro is not None:
            intros[intro[0]["evidence_id"]] = intro
    from .joint_seed_envelopes import seed_envelopes
    for index, option in seed_envelopes(payload, snapshot):
        groups[index].append(option)
    root = str(retrieval.get("_source_continuation_project_root") or "")
    from .docs_context_projection import _finalize_quality
    baseline_retrieval, baseline_payload = deepcopy(retrieval), deepcopy(payload)
    _finalize_quality(baseline_retrieval, baseline_payload, snapshot)
    old_components = set(((baseline_retrieval.get("documentation_query_plan") or {})
        .get("_component_coverage") or {}).get("covered_component_ids") or ())
    # <= 180 structural combinations, each <= 7 subsets of three citations.
    for choices in product(*groups):
        for intro in (None, *intros.values()):
            rows = [deepcopy(c[0]) for c in choices]
            bound = deepcopy(snapshot)
            for row, original, _ in choices:
                bound[row["evidence_id"]] = _snapshot_entry(original, row)
            if intro is not None:
                row, original = intro
                if len(rows) >= MAX_DOCS_SOURCES or any(row["path_or_url"] == x["path_or_url"]
                    and row["snippet"] in x["snippet"] for x in rows):
                    continue
                rows.append(deepcopy(row))
                bound[row["evidence_id"]] = _snapshot_entry(original, row)
            trial = deepcopy(payload)
            trial["sources"] = rows
            for draft, draft_bound in _draft_subsets(payload, snapshot, trial, bound, retrieval):
                finished = _finish(draft, draft_bound, retrieval, root, budget)
                if finished is None:
                    continue
                p, b, r = finished
                mapping = retained_seed_mapping(payload, snapshot, p, b)
                if not mapping or docs_context_budget_tokens(p) > budget:
                    continue
                if validate_model_visible_projection(p, snapshot=b, max_tokens=budget):
                    continue
                if not set(payload.get("covered_query_ids", [])) <= set(p.get("covered_query_ids", [])):
                    continue
                components = set(((r.get("documentation_query_plan") or {})
                    .get("_component_coverage") or {}).get("covered_component_ids") or ())
                if not old_components <= components:
                    continue
                live_ids = {row["evidence_id"] for row in p["sources"]}
                kinds = tuple(kind for row, _, kind in choices if row["evidence_id"] in live_ids)
                has_intro = intro is not None and intro[0]["evidence_id"] in live_ids
                yield p, b, r, kinds, has_intro


def select_joint_context(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int):
    """Close admitted seed units, not maximize a count of arbitrary paragraphs.

    First prefer closure of incomplete seed atoms and explicit ancestor subject
    introductions; then the cheapest feasible packet at that gain. Only when
    neither improvement exists consider a containing-section fallback. These are
    structural preferences, NOT an oracle of semantic answer completeness.
    """
    # This experiment addresses direct questions only. Explicit host lookups
    # carry a separate recovery/coverage contract; keep that producer unchanged.
    plan = retrieval.get("documentation_query_plan") or {}
    if any(q.get("origin") == "host_lookup" for q in plan.get("queries") or () if isinstance(q, dict)):
        return payload, snapshot
    closures = {}
    for row in payload.get("sources") or ():
        source = (snapshot.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(source, dict):
            continue
        options, _ = source_options(row, source)
        for alt, _, kind in options:
            if kind == "complete_atom":
                closures[row["evidence_id"]] = alt["snippet"]
    candidates = []
    for p, b, r, kinds, intro in packet_alternatives(payload, snapshot, retrieval, max_tokens=max_tokens):
        by_id = {s["evidence_id"]: s["snippet"] for s in p["sources"]}
        mapping = retained_seed_mapping(payload, snapshot, p, b)
        closed = sum(text in by_id.get(mapping.get(eid, ""), "") for eid, text in closures.items())
        coalesced = len(mapping) - len(set(mapping.values()))
        gain = (closed, coalesced, int(intro))
        fallback = any(k in {"containing_section", "seed_envelope"} for k in kinds)
        if gain != (0, 0, 0) or fallback:
            candidates.append((gain, docs_context_budget_tokens(p), p, b, r, kinds, fallback))
    useful = [c for c in candidates if c[0] != (0, 0, 0)]
    if useful:
        best_gain = max(c[0] for c in useful)
        viable = [c for c in useful if c[0] == best_gain]
    else:
        viable = [c for c in candidates if c[6]]
    if not viable:
        return payload, snapshot
    chosen = min(viable, key=lambda c: (c[1], c[5]))
    _, cost, result, bindings, r, kinds, _ = chosen
    mapping = retained_seed_mapping(payload, snapshot, result, bindings)
    retrieval.clear()
    retrieval.update(r)
    retrieval.setdefault("retrieval_diagnostics", {}).setdefault("docs_context_projection", {})["joint_structural"] = {
        "candidates": len(candidates), "closed_seed_atoms": chosen[0][0],
        "coalesced_seed_ids": {a: b for a, b in mapping.items() if a != b},
        "ancestor_introduction": bool(chosen[0][2]), "kinds": list(kinds), "budget_tokens": cost,
    }
    return result, bindings
