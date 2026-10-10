"""Materialize reviewed frame-symbol decisions with static reference evidence.

This is an audit manifest, not a runtime semantic classifier. Decisions below
apply only to the pinned modules reviewed in P0; additions fail closed.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


BASE = Path("v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06")
# Explicit technical portions; all other reviewed symbols are named below by role.
TECHNICAL = {
    "question_frame_core.py": {"InventoryKind", "QuestionClause", "InventoryFrame", "RequirementsFrame", "ActionFrame", "_trim_clause", "__all__"},
    "question_plan.py": {"_CONFIG_TARGET_RE", "_normal_subject", "_unresolved_compound", "__all__"},
    "question_plan_command_rules.py": {"__all__"},
    "question_plan_core.py": {"PlanKind", "PlannedFacet", "QuestionPlan", "Rule", "_span_pattern", "_bind_plan_to_clause", "_bind_whole_plan", "__all__"},
    "question_plan_proof.py": {"PlannedProof", "_has", "_AUTHORITATIVE", "_source_identity", "_proposition_clauses", "_REQUIREMENT_CONTENT_WORD_RE", "__all__"},
    "question_plan_surface_rules.py": {"__all__"},
    "question_retrieval_needs.py": {"RetrievalNeed", "_locate_need_span", "_masked_quotations", "_sentence_ranges", "__all__"},
    "question_semantic_frames.py": {"ComparisonFrame", "LocationFrame", "ConditionFrame", "PremiseFrame", "DecisionFrame", "ArgumentValueFrame", "ContractScopeFrame", "PurposeBehaviorFrame", "BeforeBehaviorFrame", "__all__"},
}
MIXED = {
    "question_frame_core.py": {"clean_phrase", "split_question_clause_spans", "split_question_clauses", "semantic_tail_is_safe"},
    "question_plan.py": {"_SPECIFIC_RULES", "_GENERIC_RULES", "_reusable_frame_plan", "_guard_plan_subjects", "_compile_specific_question", "_compile_generic_question", "_compile_atomic_question", "_combine_clause_plans", "_prefix_plan_is_owned", "_recognized_prefix_residue_plan", "_compile_question_plan_core", "compile_question_plan"},
    "question_plan_command_rules.py": set(),
    "question_plan_core.py": {"_finalize_full_span_coverage", "_technical", "_normalized_clause", "_unsafe_free_text"},
    "question_plan_proof.py": {"_planned_subject_score", "_requirement_item_count", "_subject_bound_requirement_tail", "_structured_requirement_proof", "relation_proof", "usage_proof", "workflow_proof", "behavior_proof"},
    "question_plan_surface_rules.py": set(),
    "question_retrieval_needs.py": {"retrieval_needs", "_cached_retrieval_needs"},
    "question_semantic_frames.py": set(),
}


def main() -> None:
    manifest = json.loads((BASE / "archives/p0-transition-manifest.json").read_text())
    references = {}
    for path in sorted(Path("docmancer").rglob("*.py")):
        tree = ast.parse(path.read_bytes())
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                references.setdefault(node.id, []).append({"path": str(path), "line": node.lineno})
    rows = []
    for row in manifest["frame_symbols"]:
        path = Path(row["path"])
        name = row["symbol"].split(":", 1)[0].strip()
        if path.name not in TECHNICAL:
            raise ValueError(f"Unreviewed module: {path}")
        if name in TECHNICAL[path.name]:
            decision = "TECHNICAL-RETAIN-CANDIDATE"
            reason = "DTO/enum/span/source-metadata or literal structural parsing; does not independently infer NL meaning"
        elif name in MIXED[path.name]:
            decision = "SPLIT"
            reason = "Caller/composition/proof adapter mixes semantic parser dependencies with span/completeness/source guarantees; remove semantic dependency, preserve guarantees"
        else:
            decision = "REMOVE-SEMANTIC-RULE"
            reason = "Reviewed NL surface/frame/lexical meaning or product-specific matcher; migrate capabilities before removal"
        rows.append({"path": str(path), "symbol": name, "line": row["line"], "kind": row["kind"],
                     "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "group": "D25" if path.name != "question_plan_proof.py" else "D23/D25",
                     "audit_decision": decision, "reason": reason,
                     "static_name_references": references.get(name, []),
                     "reachability": "Used or exported by QuestionPlan/legacy proof; conservative retain in migration scope; name references are not a resolved dynamic call graph",
                     "implementation_status": "OPEN", "owner_exception_approval": "PENDING"})
    assert len(rows) == 157
    result = {"schema": "p0-reviewed-frame-symbols-v1", "rows": rows,
              "review_basis": "Complete source read of eight frame modules; decisions materialized by this audit-only script",
              "limitations": "Technical candidates are not approved semantic exemptions; name references can collide and omit attribute/dynamic calls; implementation is unchanged"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
