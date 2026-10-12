"""Experimental pre-publication packet alternatives, never additional retrieval."""
from __future__ import annotations

from copy import deepcopy
from itertools import chain, product, combinations, islice

from .joint_context_candidates import source_options
from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
from .joint_context_lineage import _occurrence, retained_seed_mapping
from .model_visible_projection import (
    _refresh_estimate, _snapshot_entry,
    docs_context_budget_tokens, validate_model_visible_projection,
)
from .source_continuation import (
    prepare_docs_context_read_next, attach_docs_context_read_next,
    attach_source_continuation_locators, _read_next_row,
)
from .context_selection import attributable_query_ids, merge_query_matches
from .query_trace import query_trace_enabled


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


def _finish(payload: dict, snapshot: dict, retrieval: dict, root: str, budget: int | None):
    # Ordinary quality/capability primitives on private clones. The real handler
    # registers only the winning DTO, not these candidate drafts.
    from .docs_context_projection import _finalize_quality, _strip_legacy_locators
    p, b, r = deepcopy(payload), deepcopy(snapshot), deepcopy(retrieval)
    p["read_next"] = []
    b.pop("__read_next__", None)
    _strip_legacy_locators(p, b)
    _finalize_quality(r, p, b)
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
    subsets = (rows for n in range(1, len(trial["sources"]))
               for rows in combinations(trial["sources"], n))
    for rows in islice(subsets, 6):
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


def packet_alternatives(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int | None):
    """Yield validated candidates with bounded work, not bounded representation."""
    if (payload.get("kind") != "docs_context" or payload.get("support_status") != "retrieval_only"
        or any(payload.get(k) is not False for k in ("answer_supported", "answer_available", "edit_ready"))
        or (payload.get("context_quality") or {}).get("status") == "checked"
        or not payload.get("sources")):
        return
    # Validate the admitted seed before any draft can rebind its projected row.
    # Otherwise a forged line range could become its own canonical snapshot.
    if validate_model_visible_projection(payload, snapshot=snapshot):
        return
    budget = max_tokens
    plan = retrieval.get("documentation_query_plan") or {}
    lookup = any(q.get("origin") == "host_lookup" for q in plan.get("queries") or ()
                 if isinstance(q, dict))
    groups, intros = [], {}
    for row in payload["sources"]:
        original = (snapshot.get(row["evidence_id"]) or {}).get("source")
        if not isinstance(original, dict):
            return
        options, intro = source_options(row, original)
        if lookup:
            # Repair clipped lookup units without importing unrelated sections.
            options = [option for option in options if option[2] in {"original", "complete_atom"}]
            intro = None
        groups.append(options)
        if intro is not None:
            intros[intro[0]["evidence_id"]] = intro
    from .joint_seed_envelopes import seed_envelopes
    if not lookup:
        for index, option in seed_envelopes(payload, snapshot):
            groups[index].append(option)
    root = str(retrieval.get("_source_continuation_project_root") or "")
    from .docs_context_projection import _finalize_quality
    baseline_retrieval, baseline_payload = deepcopy(retrieval), deepcopy(payload)
    _finalize_quality(baseline_retrieval, baseline_payload, snapshot)
    old_components = set(((baseline_retrieval.get("documentation_query_plan") or {})
        .get("_component_coverage") or {}).get("covered_component_ids") or ())
    # Optional optimization work, not a representation limit. Exhaustion leaves
    # the admitted baseline intact; larger packets never widen Cartesian work.
    # Try the preferred closure for every seed before optional combinations.
    # Mixed sections retain dependencies; plain list/lookup groups have only
    # narrow atom alternatives. Work exhaustion must not hide this full draft.
    closed_choices = tuple(next(
        (option for option in group if option[2] == "containing_section"),
        next((option for option in group if option[2] == "complete_atom"), group[0]),
    ) for group in groups)
    drafts = 0
    work = None
    if query_trace_enabled():
        work = {"draft_attempts": 0, "finish_rejections": 0, "lineage_rejections": 0,
                "validation_rejections": 0, "coverage_rejections": 0, "yielded": 0}
        retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
            "docs_context_projection", {})["joint_work"] = work
    for choices in islice(chain((closed_choices,), product(*groups)), 180):
        for intro in (None, *intros.values()):
            rows = [deepcopy(c[0]) for c in choices]
            bound = deepcopy(snapshot)
            for row, original, _ in choices:
                bound[row["evidence_id"]] = _snapshot_entry(original, row)
            if intro is not None:
                row, original = intro
                if any(row["path_or_url"] == x["path_or_url"]
                    and row["snippet"] in x["snippet"] for x in rows):
                    continue
                rows.append(deepcopy(row))
                bound[row["evidence_id"]] = _snapshot_entry(original, row)
            trial = deepcopy(payload)
            trial["sources"] = rows
            for draft, draft_bound in islice(_draft_subsets(payload, snapshot, trial, bound, retrieval), 7):
                if drafts >= 1260:
                    return
                drafts += 1
                if work is not None:
                    work["draft_attempts"] += 1
                finished = _finish(draft, draft_bound, retrieval, root, budget)
                if finished is None:
                    if work is not None:
                        work["finish_rejections"] += 1
                    continue
                p, b, r = finished
                mapping = retained_seed_mapping(payload, snapshot, p, b)
                if not mapping:
                    if work is not None:
                        work["lineage_rejections"] += 1
                    continue
                if validate_model_visible_projection(p, snapshot=b, max_tokens=budget):
                    if work is not None:
                        work["validation_rejections"] += 1
                    continue
                if not set(payload.get("covered_query_ids", [])) <= set(p.get("covered_query_ids", [])):
                    if work is not None:
                        work["coverage_rejections"] += 1
                    continue
                components = set(((r.get("documentation_query_plan") or {})
                    .get("_component_coverage") or {}).get("covered_component_ids") or ())
                if not old_components <= components:
                    if work is not None:
                        work["coverage_rejections"] += 1
                    continue
                live_ids = {row["evidence_id"] for row in p["sources"]}
                kinds = tuple(kind for row, _, kind in choices if row["evidence_id"] in live_ids)
                has_intro = intro is not None and intro[0]["evidence_id"] in live_ids
                if work is not None:
                    work["yielded"] += 1
                yield p, b, r, kinds, has_intro


def select_joint_context(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int | None):
    """Close source dependencies, then minimize the whole public packet.

    Standalone bullet items need no sibling expansion. Mixed sections keep the
    prior conservative closure; structure alone cannot prove their prose/rules
    unnecessary. Lookup closure never imports surrounding section dependencies.
    Canonical seed bytes, source policies and explicit budgets remain mandatory.
    """
    plan = retrieval.get("documentation_query_plan") or {}
    lookup = any(q.get("origin") == "host_lookup" for q in plan.get("queries") or ()
                 if isinstance(q, dict))
    closures, sections = [], []
    for row in payload.get("sources") or ():
        source = (snapshot.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(source, dict):
            continue
        options, _ = source_options(row, source)
        for alt, original, kind in options:
            if kind == "complete_atom":
                closures.append(_occurrence(
                    alt, {alt["evidence_id"]: _snapshot_entry(original, alt)},
                ))
            elif kind == "containing_section" and not lookup:
                sections.append(_occurrence(
                    alt, {alt["evidence_id"]: _snapshot_entry(original, alt)},
                ))
    best = None
    count = 0
    for p, b, r, kinds, intro in packet_alternatives(payload, snapshot, retrieval, max_tokens=max_tokens):
        occurrences = [_occurrence(row, b) for row in p["sources"]]
        def contained(target):
            return target is not None and any(
                current is not None and current[0] == target[0]
                and current[1] <= target[1] < target[2] <= current[2]
                for current in occurrences
            )
        closed = sum(contained(target) for target in closures)
        closed_sections = sum(contained(target) for target in sections)
        cost = docs_context_budget_tokens(p)
        rank = (-closed_sections, -closed, cost, kinds)
        count += 1
        if best is None or rank < best[0]:
            best = (rank, p, b, r, intro)
    if best is None:
        return payload, snapshot
    (negative_sections, negative_closed, cost, kinds), result, bindings, r, intro = best
    mapping = retained_seed_mapping(payload, snapshot, result, bindings)
    work = ((retrieval.get("retrieval_diagnostics") or {}).get("docs_context_projection") or {}).get("joint_work")
    retrieval.clear()
    retrieval.update(r)
    if work is not None:
        retrieval.setdefault("retrieval_diagnostics", {}).setdefault("docs_context_projection", {})["joint_work"] = work
    retrieval.setdefault("retrieval_diagnostics", {}).setdefault("docs_context_projection", {})["joint_structural"] = {
        "candidates": count, "closed_seed_sections": -negative_sections,
        "closed_seed_atoms": -negative_closed,
        "coalesced_seed_ids": {a: b for a, b in mapping.items() if a != b},
        "ancestor_introduction": bool(intro), "kinds": list(kinds), "budget_tokens": cost,
    }
    return result, bindings
