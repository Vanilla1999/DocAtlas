"""Compare the metadata extraction with the committed pre-refactor policy.

Run from the repository root using the project Python environment.
This is policy equivalence, not public-packet or multilingual recall evaluation.
"""
import ast
import itertools
import hashlib
import json
import subprocess
import sys
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import patch

from docmancer.docs.domain.evidence_qualification import (
    evidence_policy_rejection_reason,
)
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows


def main():
    baseline = "d521b358"
    source = subprocess.check_output([
        "git", "show", baseline + ":docmancer/docs/domain/evidence_qualification.py",
    ], text=True)
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "evidence_policy_rejection_reason")
    namespace = {"lifecycle_allows": lifecycle_allows}
    exec("from __future__ import annotations\n" + ast.unparse(function), namespace)
    old_policy = namespace[function.name]
    count = 0
    for identity, stale, freshness, index, risk, lifecycle in itertools.product(
        (None, "", "project", "other"), (False, True),
        ("current", "stale"), ("synchronized", "pending"),
        ([], ["unsafe"]), ("active", "superseded"),
    ):
        candidate = {
            "project_identity": identity, "source_class": "project_doc",
            "stale": stale, "freshness": freshness, "index_freshness": index,
            "risk_flags": risk, "lifecycle_status": lifecycle,
        }
        for expected, intent, text, forbidden in itertools.product(
            (None, "project"), ("current", "historical", "either"),
            ("budget", "Бюджет", "presupuesto", "予算", "ميزانية"), (False, True),
        ):
            kwargs = dict(
                visible_text=text, candidate=candidate,
                expected_project_identity=expected, lifecycle_intent=intent,
                catalog_role="supporting", forbidden_catalog_roles=("supporting",)
                if forbidden else (),
                forbidden_evidence_terms=(text,) if forbidden else (),
            )
            probe = {"forbidden_evidence_terms": ["budget"]}
            before = old_policy(probe, **kwargs)
            after = evidence_policy_rejection_reason(probe, **kwargs)
            assert before == after, (kwargs, before, after)
            count += 1
    for candidate in (None, {}, {"stale": True}):
        for expected in (None, "project"):
            kwargs = dict(visible_text="text", candidate=candidate,
                          expected_project_identity=expected)
            assert old_policy({}, **kwargs) == evidence_policy_rejection_reason({}, **kwargs)
            count += 1
    print(f"PASS: {count} policy comparisons against {baseline}")
    check_projection_equivalence(old_policy)


def check_projection_equivalence(old_policy):
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval

    lookup = _host_lookup_context_retrieval()
    original = deepcopy(lookup)
    original["documentation_query_plan"]["queries"] = [
        {"query_id": "query-original", "origin": "original", "text": "project purpose documentation"},
    ]
    original["documentation_query_plan"]["query_ids"] = ["query-original"]
    original["documentation_query_plan"]["original_question"] = "project purpose documentation"
    original["documentation_query_plan"]["public_query_ids"] = ["query-original"]
    original["context_pack"] = original["context_pack"][:1]
    original["context_pack"][0]["retrieval_query_matches"] = {
        "query-original": {"query_text": "project purpose documentation"},
    }
    original["context_pack"][0]["retrieval_query_ids"] = ["query-original"]
    exact = deepcopy(lookup)
    question = "In docs/settings.md, explain ALPHA_KEY."
    exact["documentation_query_plan"].update(
        original_question=question, explicit_paths=["docs/settings.md"],
        required_query_ids=[], public_query_ids=["query-original", "query-path-1"],
        queries=[
            {"query_id": "query-original", "text": question, "origin": "original"},
            {"query_id": "query-path-1", "text": "docs/settings.md", "origin": "exact_path"},
        ],
    )
    exact["context_pack"] = exact["context_pack"][:1]
    exact["context_pack"][0].update(
        path="docs/settings.md", content="ALPHA_KEY enables durable storage.",
        line_start=11, retrieval_query_matches={}, retrieval_query_ids=[],
    )
    for name, retrieval in (("original", original), ("lookup", lookup), ("exact_path", exact)):
        current = project_docs_context(retrieval=deepcopy(retrieval))
        assert current[0]["sources"], (name, "fixture must exercise actual evidence")
        assert validate_model_visible_projection(current[0], snapshot=current[1], max_tokens=800) == []
        with ExitStack() as stack:
            for module in list(sys.modules.values()):
                if module is not None and getattr(module, "__name__", "").startswith("docmancer."):
                    if getattr(module, "evidence_policy_rejection_reason", None) is evidence_policy_rejection_reason:
                        stack.enter_context(patch.object(module, "evidence_policy_rejection_reason", old_policy))
            previous = project_docs_context(retrieval=deepcopy(retrieval))
        assert previous == current, (name, "policy extraction changed packet or snapshot")
        digest = hashlib.sha256(json.dumps(current, sort_keys=True, ensure_ascii=False,
                                         default=str).encode()).hexdigest()
        print(f"PROJECTION {name}: {digest}")
    print("PASS: original/lookup/exact_path packets and snapshots match baseline policy; M2 held fixed")


if __name__ == "__main__":
    main()
