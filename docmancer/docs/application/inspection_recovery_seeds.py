"""Read-only seeds from qualified literal hints, never visible answer evidence."""
from docmancer.docs.domain.query_script_runs import mixed_script_phrases
from .joint_context_candidates import _verified_document
from .model_visible_projection import _docs_source


def inspection_recovery_seeds(retrieval: dict) -> list[tuple[dict, dict]]:
    """Offer only current-call qualified hints from the unchanged mixed query.

    Empty projection need not mean the document is inaccessible. A qualified
    optional hint may authorize bounded inspection, but not original coverage.
    The caller must still rebind and apply all policies to the proposed range.
    """
    from .docs_context_projection import _requalify_visible_source
    plan = retrieval.get("documentation_query_plan") or {}
    if retrieval.get("hard_stop") or plan.get("explicit_paths") or plan.get("_component_contract"):
        return []
    literals = set(mixed_script_phrases(str(plan.get("original_question") or "")))
    hints = {q["query_id"]: q["text"] for q in plan.get("queries") or []
             if q.get("origin") == "retrieval_hint" and q.get("text") in literals
             and q.get("coverage_required") is False and not q.get("public_parent_query_id")}
    identity = retrieval.get("project_identity")
    if not identity:
        identities = {c.get("project_identity") for c in
                      (retrieval.get("selection_decision") or {}).get("selected_candidates", [])
                      if isinstance(c, dict) and c.get("project_identity")}
        if len(identities) == 1:
            identity = next(iter(identities))
    if not hints or not identity:
        return []
    out, seen = [], set()
    for source in (retrieval.get("context_pack") or ())[:32]:
        if not isinstance(source, dict) or source.get("project_identity") != identity:
            continue
        if source.get("source_class") != "project_doc":
            continue
        if not any(q in hints for q in source.get("retrieval_query_matches") or {}):
            continue
        row = _docs_source(source)
        if row is None:
            continue
        row.update(project_identity=identity, line_start=source.get("line_start"),
                   line_end=source.get("line_end"), authority=source.get("authority"),
                   scope=source.get("doc_scope") or source.get("scope"))
        if _verified_document(source, row) is None:
            continue
        checked = _requalify_visible_source({**source, **row, "_qualification_candidate": source,
            "_expected_project_identity": identity}, query_text=hints)
        if not any((checked.get("retrieval_query_matches") or {}).get(q, {}).get("qualified") is True
                   for q in hints):
            continue
        key = (row["path_or_url"], source.get("_source_snapshot_sha256"))
        if key in seen:
            continue
        seen.add(key)
        out.append((row, source))
        if len(out) == 3:
            break
    return out
