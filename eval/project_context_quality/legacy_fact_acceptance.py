"""Independent Legacy fact acceptance; production query credit remains telemetry.

The observer copies one real call's validator material. The oracle uses frozen
case bytes and visible source text, never producer fact_checks or semantic labels.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "eval/project_context_quality/cases.json"
PROTOCOL_PATH = CORPUS_PATH.with_name("protocol.lock.json")
ORACLE_SCHEMA = "legacy-source-fact-oracle-result-v1"
EVIDENCE_SCHEMA = "legacy-same-call-source-evidence-v1"
FACT_METRIC = "verified_original_case_fact_count"
_TRACE_FIELDS = (
    "query_text", "query_origin", "relation", "qualified", "admission_only",
    "context_only", "public_parent_query_id", "derived_from_query_id",
    "derived_from_query_ids", "coverage_kind", "coverage_kinds",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require(condition: bool, guard: str) -> None:
    if not condition:
        raise ValueError(guard)


def frozen_legacy_cases() -> tuple[dict[str, Any], ...]:
    raw = CORPUS_PATH.read_bytes()
    lock = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    corpus = json.loads(raw)
    rows = corpus.get("cases") or []
    _require(
        corpus.get("schema_version") == "project-context-quality-corpus-v1"
        and lock.get("schema_version") == "project-context-quality-protocol-v1"
        and hashlib.sha256(raw).hexdigest() == lock.get("case_file_sha256")
        and CORPUS_PATH.with_name("cases.legacy.json").read_bytes() == raw
        and [row.get("id") for row in rows] == lock.get("case_ids")
        and len(rows) == lock.get("case_count") == 16
        and len({row.get("id") for row in rows}) == 16,
        "legacy_frozen_corpus_binding",
    )
    return tuple(rows)


def capture_legacy_evidence(arguments: dict, payload: dict, snapshot: dict) -> dict:
    """Copy existing observations; do not retrieve, validate, qualify or score again."""
    bindings = {}
    for evidence_id, bound in snapshot.items():
        if not isinstance(bound, dict):
            continue
        source = bound.get("source") or {}
        matches = (bound.get("qualification") or {}).get("retrieval_query_matches") or {}
        bindings[evidence_id] = {
            "projected_source": deepcopy(bound.get("projected_source")),
            "source_hash_material": deepcopy({
                "path": source.get("path") or source.get("source") or source.get("url") or source.get("source_url"),
                "section": source.get("heading_path") or source.get("title"),
                "content": source.get("content") or source.get("display_text"),
                "snippet": source.get("snippet") or source.get("code"),
                "version": source.get("version_binding") or source.get("version") or source.get("requested_version"),
            }),
            "retrieval_query_matches": {
                query_id: {key: deepcopy(trace[key]) for key in _TRACE_FIELDS if key in trace}
                for query_id, trace in matches.items() if isinstance(trace, dict)
            },
        }
    return {
        "schema_version": EVIDENCE_SCHEMA,
        "request": deepcopy({
            "question": arguments.get("question"),
            "scope": arguments.get("scope"),
            "lookup_queries": arguments.get("lookup_queries", []),
            "project_path": arguments.get("project_path"),
        }),
        "observer_counts": deepcopy((payload.get("diagnostics") or {}).get("observer_counts")),
        "source_bindings": bindings,
    }


def _bound_sources(case: dict, row: dict, source_root: Path) -> tuple[list[dict], dict]:
    receipt = row.get("legacy_fact_evidence") or {}
    request = receipt.get("request") or {}
    _require(
        receipt.get("schema_version") == EVIDENCE_SCHEMA
        and row.get("question") == request.get("question") == case["question"]
        and row.get("scope") == request.get("scope") == case.get("scope", "project")
        and request.get("lookup_queries") == case.get("lookup_queries", [])
        and isinstance(request.get("project_path"), str) and bool(request["project_path"]),
        "legacy_literal_request_binding",
    )
    host_root = Path(request["project_path"])
    _require(
        host_root.is_absolute() and ".." not in host_root.parts,
        "legacy_literal_project_root",
    )
    expected_identity = "local:" + hashlib.sha256(str(host_root).encode("utf-8")).hexdigest()
    counts = receipt.get("observer_counts") or {}
    _require(
        set(counts) == {"retrieval_calls", "validation_calls"}
        and all(type(counts[key]) is int and counts[key] == 1 for key in counts),
        "legacy_same_call_observation",
    )
    payload = row.get("payload") or {}
    sources = payload.get("sources", [])
    bindings = receipt.get("source_bindings")
    _require(isinstance(sources, list) and isinstance(bindings, dict), "legacy_source_inventory")
    seen = set()
    for source in sources:
        _require(isinstance(source, dict), "legacy_source_inventory")
        evidence_id = source.get("evidence_id")
        _require(
            isinstance(evidence_id, str) and bool(evidence_id) and evidence_id not in seen,
            "legacy_source_inventory",
        )
        seen.add(evidence_id)
        bound = bindings.get(evidence_id) or {}
        material = bound.get("source_hash_material") or {}
        _require(bound.get("projected_source") == source, "legacy_exact_snapshot_projection")
        _require(source.get("project_identity") == expected_identity, "legacy_host_project_identity")
        _require(source.get("scope") == request["scope"] == "project", "legacy_project_scope")
        _require(
            set(material) == {"path", "section", "content", "snippet", "version"}
            and hashlib.sha256(_canonical(material)).hexdigest() == source.get("content_sha256")
            and material["path"] == source.get("path_or_url")
            and str(material["section"] or "document").strip() == source.get("section")
            and str(material["version"] or "unversioned") == source.get("version_binding"),
            "legacy_source_hash_binding",
        )
        path, snippet = source.get("path_or_url"), source.get("snippet")
        _require(
            isinstance(path, str) and bool(path) and isinstance(snippet, str) and bool(snippet.strip()),
            "legacy_visible_source_bytes",
        )
        _require(
            any(isinstance(material[key], str) and snippet in material[key]
                for key in ("content", "snippet")),
            "legacy_visible_source_bytes",
        )
        target = (source_root / path).resolve()
        _require(
            target.is_relative_to(source_root.resolve()) and target.is_file(),
            "legacy_current_source_bytes",
        )
        current_text = target.read_bytes().decode("utf-8")
        _require(snippet in current_text, "legacy_current_source_bytes")
        lines = current_text.split("\n")
        first, last = source.get("line_start"), source.get("line_end")
        _require(
            type(first) is int and type(last) is int and 1 <= first <= last <= len(lines)
            and last == first + snippet.count("\n")
            and snippet in "\n".join(lines[first - 1:last]),
            "legacy_current_line_span",
        )
        _require(
            not any(path.startswith(prefix) for prefix in (
                "eval/", "docs/analysis/", ".hermes/plans/", "roadmap/",
                *case.get("forbidden_source_prefixes", []),
            )),
            "legacy_forbidden_source",
        )
    return sources, bindings


def _original_credit(case: dict, row: dict, sources: list[dict], bindings: dict) -> bool:
    payload = row.get("payload") or {}
    covered, missing = payload.get("covered_query_ids", []), payload.get("missing_query_ids", [])
    expected = {"query-original", *(f"query-lookup-{index}" for index in range(1, len(case.get("lookup_queries", [])) + 1))}
    _require(
        isinstance(covered, list) and isinstance(missing, list)
        and all(isinstance(value, str) for value in (*covered, *missing))
        and len(set(covered)) == len(covered) and len(set(missing)) == len(missing)
        and not set(covered).intersection(missing)
        and (not covered and not missing or set((*covered, *missing)) == expected),
        "legacy_public_query_inventory",
    )
    claimed = "query-original" in covered
    attributed = False
    for source in sources:
        trace = ((bindings[source["evidence_id"]].get("retrieval_query_matches") or {}).get("query-original") or {})
        if (
            trace.get("qualified") is True and not trace.get("admission_only")
            and trace.get("query_text") == case["question"]
            and trace.get("query_origin") == "original" and trace.get("relation") == "direct"
            and not any(trace.get(key) for key in (
                "public_parent_query_id", "derived_from_query_id", "derived_from_query_ids",
            ))
        ):
            attributed = True
    _require(not claimed or attributed, "legacy_no_lookup_to_original_transfer")
    observed = row.get("observed") or {}
    if case["expected_kind"] != "insufficient_evidence":
        _require(
            observed.get("original_query_covered") is (claimed and attributed),
            "legacy_raw_original_telemetry_binding",
        )
    return claimed and attributed


def _substantive_fact_text(snippet: str) -> str:
    """Keep source statements/code/data rows; metadata cannot supply a frozen fact."""
    lines = snippet.splitlines()
    body = []
    fence = ""
    for index, line in enumerate(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = ""
            else:
                body.append(line)
            continue
        if marker:
            fence = marker[1]
            continue
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if (
            line.lstrip().startswith("#") or re.fullmatch(r"[=-]{3,}", following)
            or ("|" in line and re.fullmatch(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?", following))
            or re.match(r"^\s*\[[^\]]+\]:\s*\S+", line)
        ):
            continue
        # Mask metadata in place: removing it must not manufacture a new fact.
        code_spans = [(match.start(), match.end()) for match in re.finditer(r"(`+)(.+?)\1", line)]
        outside, visible = list(line), list(line)
        for pattern, kind in (
            (r"!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", "image"),
            (r"(?<!!)\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])", "link"),
            (r"https?://\S+", "url"),
        ):
            for match in re.finditer(pattern, line):
                if any(start <= match.start() < end for start, end in code_spans):
                    continue
                for offset in range(match.start(), match.end()):
                    outside[offset] = "\x00"
                    if kind != "link" or not match.start(1) <= offset < match.end(1):
                        visible[offset] = "\x00"
        statement = "".join(outside).strip(" \t-*+0123456789.)|:<>_=")
        if re.search(r"[^\W_]", statement, re.UNICODE):
            body.append("".join(visible))
    return "\n".join(body)


def _inspect_case(case: dict, row: dict, source_root: Path) -> tuple[bool, bool]:
    sources, bindings = _bound_sources(case, row, source_root)
    payload = row.get("payload") or {}
    _require(
        payload.get("kind") != "docs_answer" and not payload.get("answer")
        and all(payload.get(flag) is None or payload.get(flag) is False for flag in (
            "answer_supported", "answer_available", "edit_ready", "mutation_ready",
        )),
        "legacy_no_answer_or_edit_authority",
    )
    if case["expected_kind"] == "insufficient_evidence":
        _require(payload.get("status") == "insufficient_evidence", "legacy_negative_abstention")
        return False, _original_credit(case, row, sources, bindings)
    original = _original_credit(case, row, sources, bindings)
    ready = (
        payload.get("status") == "ok" and payload.get("kind") == "docs_context"
        and payload.get("context_status") == "ready" and payload.get("answer_policy") == "cite_only"
        and all(payload.get(flag) is False for flag in ("answer_supported", "answer_available", "edit_ready"))
        and isinstance(payload.get("facets"), list)
        and set((*payload.get("covered_query_ids", []), *payload.get("missing_query_ids", [])))
            == {"query-original", *(f"query-lookup-{index}" for index in range(1, len(case.get("lookup_queries", [])) + 1))}
    )
    source_ids = {source["evidence_id"] for source in sources}
    facet_ids = {
        value for facet in payload.get("facets", []) if isinstance(facet, dict)
        for value in facet.get("evidence_ids", [])
    }
    _require(facet_ids.issubset(source_ids), "legacy_visible_reference_binding")
    allowed = set(case.get("allowed_paths") or case.get("sources") or [])
    facts = case.get("required_facts") or []
    all_facts = bool(facts) and all(
        any(
            source["path_or_url"] == fact["source"] and fact["source"] in allowed
            and fact["text"].casefold() in _substantive_fact_text(source["snippet"]).casefold()
            for source in sources
        )
        for fact in facts
    )
    return bool(
        ready and all_facts and all(source["path_or_url"] in allowed for source in sources)
    ), original


def summarize_legacy_facts(report: dict, *, source_root: Path = ROOT) -> dict:
    """Recompute the frozen original-case fact count without reading any claimed rollup."""
    cases = frozen_legacy_cases()
    summary = {
        "schema_version": ORACLE_SCHEMA,
        FACT_METRIC: 0,
        "positive_case_count": 15,
        "verified_case_ids": [],
        "raw_original_query_covered_count": 0,
        "errors": [],
    }
    rows = report.get("results") or []
    if not (
        report.get("schema_version") == "project-answer-quality-live-result-v1"
        and report.get("run_mode") == "live_self_host" and report.get("provider_free") is True
        and report.get("lane") == "legacy" and report.get("input_mode") == "question_with_lookups"
        and report.get("corpus_sha256") == hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
        and all(type(report.get(key)) is int and report[key] == expected for key, expected in (
            ("case_count", 16), ("positive_case_count", 15), ("negative_case_count", 1),
        ))
        and isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
        and [row.get("case_id") for row in rows] == [case["id"] for case in cases]
    ):
        summary["errors"].append("legacy_frozen_report_inventory")
        return summary
    for case, row in zip(cases, rows):
        try:
            complete, original = _inspect_case(case, row, source_root)
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            guard = str(exc) if isinstance(exc, ValueError) else "legacy_malformed_case_evidence"
            summary["errors"].append(f"{case['id']}:{guard}")
            continue
        if case["expected_kind"] != "insufficient_evidence":
            summary["raw_original_query_covered_count"] += int(original)
        if complete:
            summary["verified_case_ids"].append(case["id"])
    summary[FACT_METRIC] = len(summary["verified_case_ids"])
    return summary
