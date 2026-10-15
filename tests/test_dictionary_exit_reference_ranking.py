"""New-only dictionary exit checks; literal resolution is not topic inference."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib

import pytest

from docmancer.docs.application import context_candidate_ranking as ranking
from docmancer.docs.domain.query_reference_binding import (
    CatalogSource, ScopeKey, normalize_reference_path, prepare_reference_probe,
    query_mentions, reference_body_question, resolve_references,
)
from docmancer.docs.domain.question_retrieval_needs import _need_subject
from docmancer.docs.domain.evidence_qualification import qualify_evidence


SCOPE = ScopeKey("repo:literal", "v2", "snapshot:literal")


def catalog(path="docs/Guide.md", identity="guide", scope=SCOPE):
    return CatalogSource(identity, scope, path, "a" * 64)


def reference(question, rows, **kwargs):
    plan = resolve_references(question, catalog=rows, scope=SCOPE, **kwargs)
    return next(ref for ref in plan.references if ref.role == "source_locator")






















def prepared_case(question="docs/Guide.md `Client.send`", raw="# Guide\n\nClient.send returns a value.\n", path="docs/Guide.md"):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    row = replace(catalog(path), content_sha256=digest)
    plan = asdict(resolve_references(question, catalog=[row], scope=SCOPE))
    candidate = {
        "project_identity": SCOPE.project_id, "generation_id": SCOPE.snapshot_id,
        "resolved_version": SCOPE.version, "path": row.canonical_path,
        "source_content_hash": digest, "char_start": 0, "char_end": len(raw),
        "_reference_root_plan": plan, "_reference_plans": {question: plan},
        "_reference_evidence": {"schema_version": 1, "source": asdict(row),
            "char_start": 0, "char_end": len(raw), "text": raw, "raw_document": raw},
    }
    return {"query_text": question, "parent_exact_terms": ["guide.md", "client.send"]}, candidate, raw










def qualify_prepared(probe, row, body):
    probe = {**probe, "query_origin": "original", "relation": "direct"}
    return qualify_evidence(probe, query_id="query-original", visible_text=body,
        evidence_text=body, candidate=row, expected_project_identity=SCOPE.project_id,
        authoritative_query={"query_id": "query-original", "origin": "original",
            "relation": "direct", "text": probe["query_text"]})




















def candidate(identity, text, query_id="query-original", **trace):
    return {"evidence_id": identity, "path": "docs/guide.md", "snippet": text,
        "retrieval_query_matches": {query_id: {"qualified": True, "lexical_score": 1.0,
            "match_ratio": 1.0, "query_text": "widget", **trace}}}









