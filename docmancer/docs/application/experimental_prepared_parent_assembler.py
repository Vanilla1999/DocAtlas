"""Experiment: original verified owner sections instead of late multi-draft assembly."""
from __future__ import annotations
from copy import deepcopy
from types import SimpleNamespace
from .joint_context_candidates import _context_row, _verified_document
from .joint_context_selection import _finish
from .model_visible_projection import _snapshot_entry, validate_model_visible_projection
from .experimental_context_finalization import experimental_context_cost
from .query_trace import query_trace_enabled

MAX_PARENT_CHARS = 24000

def assemble_prepared_parents(payload: dict, snapshot: dict, retrieval: dict, *, max_tokens: int | None):
    """Try one immutable owning section per seed; retain native seed on failure.

    All candidates originate in the core live read; no retrieval, generation,
    source-name inference, query-rewriting, or additional answer authority.
    """
    if payload.get("kind") != "docs_context" or not payload.get("sources"):
        return payload, snapshot
    from docmancer.docs.domain.original_body_discovery import experimental_context_max_tokens
    cap = experimental_context_max_tokens()
    root = str(retrieval.get("_source_continuation_project_root") or "")
    current, bindings = payload, snapshot
    decisions = [] if query_trace_enabled() else None
    for evid in [s.get("evidence_id") for s in payload.get("sources") or ()]:
        visible = next((s for s in current["sources"] if s.get("evidence_id")==evid), None)
        bound = bindings.get(evid)
        original = bound.get("source") if isinstance(bound, dict) else None
        outcome = "no_verified_seed"
        if not isinstance(visible, dict) or not isinstance(original, dict):
            if decisions is not None: decisions.append(outcome)
            continue
        raw = _verified_document(original, visible)
        ref = original.get("_reference_evidence") or {}
        owner = ref.get("owner") or {}
        a,b = owner.get("scope_start"),owner.get("scope_end")
        x,y = ref.get("char_start"),ref.get("char_end")
        if (raw is None or type(a) is not int or type(b) is not int
            or type(x) is not int or type(y) is not int
            or not 0 <= a <= x < y <= b <= len(raw)):
            outcome = "owner_unavailable_or_mismatch"
        elif b-a > MAX_PARENT_CHARS: outcome = "owner_exceeds_work_cap"
        elif raw[a:b] == visible.get("snippet"): outcome = "already_owner"
        else:
            path = original.get("heading_path") or ()
            path = tuple(path) if isinstance(path,(list,tuple)) else tuple(
                item.strip() for item in str(path).split(" > ") if item.strip())
            parent=SimpleNamespace(char_start=a,char_end=b,heading_path=path,
                level=1 if owner.get("text") else 0,
                logical_id=owner.get("logical_id"),
                title=str(original.get("title") or original.get("section_title") or ""))
            proposal=_context_row(original,visible,raw,parent,a,b,supplementary=False)
            if proposal is None or visible.get("snippet","") not in raw[a:b]:
                outcome = "structural_proposal_invalid"
            else:
                row,source=proposal
                draft,bs=deepcopy(current),deepcopy(bindings)
                draft["sources"]=[row if r.get("evidence_id")==evid else r for r in draft["sources"]]
                bs[evid]=_snapshot_entry(source,row)
                final=_finish(draft,bs,retrieval,root,max_tokens)
                if final is None: outcome = "finalize_refused"
                else:
                    p,bound_now,updated=final
                    if validate_model_visible_projection(p,snapshot=bound_now,max_tokens=max_tokens):
                        outcome="projection_invalid"
                    elif cap is not None and experimental_context_cost(p)>cap:
                        outcome="final_cap"
                    else:
                        current,bindings=p,bound_now
                        retrieval.clear()
                        retrieval.update(updated)
                        outcome="owner_accepted"
        if decisions is not None: decisions.append(outcome)
    if decisions is not None:
        retrieval.setdefault("retrieval_diagnostics",{}).setdefault(
            "docs_context_projection",{})["prepared_parent_assembler"]={
            "schema_version":1,"recorded_count":len(decisions),"decisions":decisions[:32]}
    return current,bindings
