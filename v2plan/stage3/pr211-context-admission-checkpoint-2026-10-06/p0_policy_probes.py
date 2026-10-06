"""Diagnostic-only probes of current policy/parser behavior, not release tests."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

from docmancer.docs.domain.context_windows import _query_terms
from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
from docmancer.docs.domain.query_terms import documentation_technical_anchors, supplemental_query_is_useful
from docmancer.docs.domain._project_answer_contract_part01 import _cardinality


def main() -> None:
    candidate = {"project_identity": "fixture-project", "source_class": "project_doc",
                 "freshness": "current", "index_freshness": "synchronized"}
    cases = [
        ("current-source", {}, candidate, "Ordinary source text.", "reference"),
        ("wrong-project", {}, {**candidate, "project_identity": "other"}, "Ordinary source text.", "reference"),
        ("stale-source", {}, {**candidate, "stale": True}, "Ordinary source text.", "reference"),
        ("unsynchronized-source", {}, {**candidate, "index_freshness": "pending"}, "Ordinary source text.", "reference"),
        ("proposal-forbidden-role", {"forbidden_catalog_roles": ["reference"]}, candidate, "Ordinary source text.", "reference"),
        ("proposal-forbidden-term", {"forbidden_evidence_terms": ["policy"]}, candidate, "This policy is current.", "reference"),
        ("proposal-substring-term", {"forbidden_evidence_terms": ["policy"]}, candidate, "The identifier is policyCache.", "reference"),
    ]
    policy = [{"id": name, "probe": probe, "candidate": source, "visible_text": text,
               "catalog_role": role, "rejection": evidence_policy_rejection_reason(
                   probe, visible_text=text, catalog_role=role, candidate=source,
                   expected_project_identity="fixture-project")}
              for name, probe, source, text, role in cases]
    questions = ["When does project work after launch?", "Когда работает проект после запуска?"]
    literals = ["`DocAtlas`", "`NovelProduct`", "if not", "если не", "`if`"]
    counts = ["two tools and nine attempts", "nine attempts and two tools",
              "два инструмента и девять попыток", "девять попыток и два инструмента"]
    paths = ["docmancer/docs/domain/context_windows.py", "docmancer/docs/domain/query_terms.py",
             "docmancer/docs/domain/evidence_qualification.py",
             "docmancer/docs/domain/_project_answer_contract_part01.py",
             "docmancer/docs/domain/_project_answer_contract_shared.py"]
    print(json.dumps({"schema": "p0-policy-diagnostic-v1", "python": platform.python_version(),
                      "source_hashes": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
                      "policy_cases": policy,
                      "window_terms": [{"question": q, "terms": sorted(_query_terms((q,)))} for q in questions],
                      "literal_cases": [{"text": q, "anchors": documentation_technical_anchors(q),
                                         "supplemental_useful": supplemental_query_is_useful(q)} for q in literals],
                      "cardinality_cases": [{"question": q, "cardinality": _cardinality(q)} for q in counts],
                      "limitations": "Synthetic unit probes of unchanged code; not final delivery, safety certification, or approved gold."},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
