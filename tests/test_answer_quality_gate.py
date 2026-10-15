from __future__ import annotations

import copy
import math

from eval.answer_quality_gate import (
    canonical_bytes,
    compare_pareto_candidate,
    evaluate_projection_contract,
    load_case_contracts,
    load_protocol,
    protocol_manifest,
    validate_protocol,
)


def _fit_estimate(payload):
    payload["estimated_tokens"] = 0
    for _ in range(10):
        actual = max(1, math.ceil(len(canonical_bytes(payload)) / 4))
        if payload["estimated_tokens"] == actual:
            return payload
        payload["estimated_tokens"] = actual
    raise AssertionError("synthetic projection token estimate did not converge")


def _docs_contract():
    return {
        "contract_id": "synthetic-docs",
        "source_ref": "synthetic:docs",
        "taxonomy": "exact_api",
        "result_kind": "docs_answer",
        "expected_status": "ok",
        "required_answer_facts": ["Client.open"],
        "acceptable_evidence": ["docs/api.md"],
        "forbidden_claims": ["Client.openLegacy"],
        "forbidden_versions": ["1.0"],
        "exact_identifiers": ["Client.open"],
        "required_patch_fields": {},
        "required_public_commands": [],
        "maximum_visible_tokens": 800,
    }


def _docs_projection():
    source = {
        "evidence_id": "ev-docs",
        "path_or_url": "docs/api.md",
        "section": "Open",
        "snippet": "Call Client.open(config).",
        "version_binding": "2.0",
        "content_sha256": "a" * 64,
    }
    projection = _fit_estimate({
        "status": "ok",
        "kind": "docs_answer",
        "answer": "Call Client.open(config).",
        "answer_evidence_ids": ["ev-docs"],
        "sources": [source],
    })
    return projection, {"ev-docs": dict(source)}


def _patch_contract():
    return {
        "contract_id": "synthetic-patch",
        "source_ref": "synthetic:patch",
        "taxonomy": "patch_contract",
        "result_kind": "patch_context",
        "expected_status": "ok",
        "required_answer_facts": [],
        "acceptable_evidence": ["AGENTS.md", "src/worker.py"],
        "forbidden_claims": ["disable isolation"],
        "forbidden_versions": [],
        "exact_identifiers": ["Worker.run"],
        "required_patch_fields": {
            "objective": ["Update Worker.run"],
            "targets": ["src/worker.py"],
            "invariants": ["preserve isolation"],
            "checks": ["pytest tests/test_worker.py"],
        },
        "required_public_commands": ["pytest tests/test_worker.py"],
        "maximum_visible_tokens": 1500,
    }


def _patch_projection():
    policy = {
        "evidence_id": "ev-policy",
        "path_or_url": "AGENTS.md",
        "section": "Rules",
        "snippet": "Preserve isolation. Run pytest tests/test_worker.py.",
        "version_binding": "repository",
        "content_sha256": "b" * 64,
    }
    target = {
        "evidence_id": "ev-target",
        "path_or_url": "src/worker.py",
        "section": "Worker.run",
        "snippet": "def run(): pass",
        "version_binding": "repository",
        "content_sha256": "c" * 64,
    }
    projection = _fit_estimate({
        "status": "ok",
        "kind": "patch_context",
        "objective": "Update Worker.run",
        "sources": [policy, target],
        "targets": {"likely_files": ["src/worker.py"], "symbols": ["Worker.run"]},
        "invariants": [{"claim": "Preserve isolation", "evidence_ids": ["ev-policy"]}],
        "forbidden_changes": [],
        "implementation_guidance": [],
        "checks": {
            "tests": [{
                "command": "pytest tests/test_worker.py",
                "evidence_ids": ["ev-policy"],
            }]
        },
        "uncertainties": [],
    })
    return projection, {
        "ev-policy": dict(policy),
        "ev-target": dict(target),
    }











