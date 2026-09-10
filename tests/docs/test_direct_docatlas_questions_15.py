"""Exposed direct-question sidecar for the original 15 DocAtlas questions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import scripts.run_project_docs_self_host_gate as self_host_gate


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIRECT_15_PATH = _REPO_ROOT / "eval/direct_docatlas_questions_15/cases.json"


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _direct_15_payload() -> dict[str, object]:
    return json.loads(_DIRECT_15_PATH.read_text(encoding="utf-8"))


def _assert_direct_15_sidecar() -> None:
    sidecar = _direct_15_payload()
    assert sidecar["baseline_commit"] == "e179471527e009c88f77acbdaeeeeb8ad1c8d316"
    assert sidecar["request_contract"] == {
        "scope": "all",
        "lookup_queries": "absent",
        "maximum_sources": 3,
        "maximum_estimated_tokens": 800,
    }
    assert [row["id"] for row in sidecar["cases"]] == [
        f"Q{index:02d}" for index in range(1, 16)
    ]

    for source_path, metadata in sidecar["sources"].items():
        path = _REPO_ROOT / source_path
        assert path.is_file(), source_path
        assert _git_blob_sha(path) == metadata["git_blob_sha"], source_path

    cases = []
    for case in sidecar["cases"]:
        assert case["fact_groups"], case["id"]
        required_fact_groups = []
        for group in case["fact_groups"]:
            assert group["witnesses"], (case["id"], group["id"])
            alternatives = []
            for witness in group["witnesses"]:
                source_text = (_REPO_ROOT / witness["path"]).read_text(encoding="utf-8")
                assert witness["text"] in source_text, (case["id"], group["id"], witness)
                alternatives.append((witness["path"], witness["text"]))
            required_fact_groups.append(tuple(alternatives))
        cases.append((case, tuple(required_fact_groups)))

    catalog_text = (_REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")
    assert "eval/direct_docatlas_questions_15" not in catalog_text

    previous_home = os.environ.get("DOCATLAS_HOME")
    failures = {}
    call_count = 0
    try:
        with TemporaryDirectory(prefix="docatlas-direct-15-") as raw_tmp:
            tmp = Path(raw_tmp)
            os.environ["DOCATLAS_HOME"] = str(tmp / "home")
            config = self_host_gate.DocmancerConfig()
            config.index.db_path = str(tmp / "docmancer.db")
            config.index.extracted_dir = str(tmp / "extracted")
            service = self_host_gate.LibraryDocsService(
                config=config,
                config_source="explicit",
                registry=self_host_gate.LibraryRegistry(config.index.db_path),
                agent=self_host_gate.DocmancerAgent(config=config),
                job_tracker=self_host_gate.DocsJobTracker(),
            )
            sync = service.sync_project_docs(str(_REPO_ROOT), with_vectors=False)
            assert getattr(sync, "status", None) == "success"

            for case, required_fact_groups in cases:
                payload, snapshot = self_host_gate._call_with_snapshot(
                    {
                        "question": case["question"],
                        "project_path": str(_REPO_ROOT),
                        "scope": "all",
                    },
                    service,
                )
                call_count += 1
                payload = dict(payload or {})
                sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
                public_query_ids = {
                    str(value)
                    for value in (
                        *(payload.get("covered_query_ids") or ()),
                        *(payload.get("missing_query_ids") or ()),
                    )
                }
                fact_checks = {
                    f"fact-group-{index}": any(
                        str(source.get("path_or_url") or "") == path
                        and fragment.casefold() in str(source.get("snippet") or "").casefold()
                        for path, fragment in alternatives
                        for source in sources
                        if isinstance(source, dict)
                    )
                    for index, alternatives in enumerate(required_fact_groups, 1)
                }
                diagnostics = (
                    payload.get("diagnostics")
                    if isinstance(payload.get("diagnostics"), dict)
                    else {}
                )
                observer_counts = diagnostics.get("observer_counts") or {}
                checks = {
                    "status_ok": payload.get("status") == "ok",
                    "kind_matches": payload.get("kind") == "docs_context",
                    "source_backed": bool(sources),
                    "context_contract": self_host_gate._validate_context_result(payload) is None,
                    "required_facts": all(fact_checks.values()),
                    "citation_integrity": self_host_gate._citation_integrity(payload, snapshot),
                    "no_packs_contamination": not self_host_gate._packs_contamination(
                        case["question"], payload
                    ),
                    "no_lookup_queries": not any(
                        value.startswith("query-lookup-") for value in public_query_ids
                    ),
                    "source_budget": len(sources) <= 3,
                    "token_budget": int(payload.get("estimated_tokens") or 0) <= 800,
                    "retrieval_only": payload.get("answer_supported") is False
                    and payload.get("edit_ready") is False,
                    "one_retrieval_call": observer_counts.get("retrieval_calls") == 1,
                    "one_validation_call": observer_counts.get("validation_calls") == 1,
                }
                if not all(checks.values()):
                    failures[case["id"]] = {
                        "status": payload.get("status"),
                        "kind": payload.get("kind"),
                        "reason_code": payload.get("reason_code"),
                        "failed_checks": [
                            name for name, passed in checks.items() if not passed
                        ],
                        "missing_fact_groups": [
                            name for name, passed in fact_checks.items() if not passed
                        ],
                        "sources": [
                            {
                                "path": str(source.get("path_or_url") or ""),
                                "snippet": str(source.get("snippet") or "")[:1400],
                            }
                            for source in sources
                            if isinstance(source, dict)
                        ],
                        "covered_query_ids": payload.get("covered_query_ids"),
                        "missing_query_ids": payload.get("missing_query_ids"),
                        "diagnostic_keys": sorted(str(key) for key in diagnostics),
                        "diagnostics_preview": json.dumps(
                            diagnostics, sort_keys=True, default=str
                        )[:4000],
                    }
    finally:
        if previous_home is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous_home

    assert call_count == 15
    if failures:
        details = "\n".join(
            f"{case_id}: {json.dumps(failure, sort_keys=True)}"
            for case_id, failure in sorted(failures.items())
        )
        pytest.fail(f"direct-15 failures:\n{details}", pytrace=False)


def test_direct_docatlas_questions_15_visible_context_covers_all_required_facts():
    _assert_direct_15_sidecar()
