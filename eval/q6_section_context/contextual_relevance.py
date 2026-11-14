"""Evaluation-only, same-pool MiniLM controls for joint context selection.

``body`` scores each unchanged checked row with the existing complete fit-first
recipe. ``contextual`` uses that same recipe and row, adding only source-exact
headings and the own introductory bodies of its Markdown ancestors. Context is
an interpretation input, not delivered evidence or a qualification signal.

Install inside a real public read's server process. Serialized snapshots cannot
supply the current native-discovery receipt. This module never opens source
files, acquires candidates, widens the candidate pool, or reads expected facts.
The normal joint lexical eligibility, grouping, MMR and wire budget remain.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import math
import os
import sys
from typing import Any


RECIPE = "q6-joint-source-ancestor-fit-first-v1"
MODES = frozenset({"body", "contextual"})
_CALL: ContextVar[tuple[dict, dict] | None] = ContextVar("q6_checked_selection_call", default=None)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def _span(raw: str, start: int, end: int, role: str) -> dict:
    return {
        "role": role, "char_start": start, "char_end": end,
        "line_start": raw.count("\n", 0, start) + 1,
        "line_end": raw.count("\n", 0, end - 1) + 1,
        "utf8_bytes": len(raw[start:end].encode("utf-8")),
        "sha256": _digest(raw[start:end]),
    }


def _check_context_span(source: dict, raw: str, parent, span: dict, question: str, expected: str | None) -> str:
    """Apply existing canonical and same-call derivation guards, without I/O.

    This mirrors the source-only hydration proof for an exact parser-owned
    section or heading, but never projects or delivers the derived candidate.
    The caller proves the ancestor/owner relationship independently by parsing.
    """
    from docmancer.docs.domain.literal_context_admission import _checked_original_candidate
    from docmancer.docs.domain.original_body_discovery import original_body_derivation_binding
    from docmancer.docs.domain.query_reference_binding import prepare_reference_probe

    a, b = span["char_start"], span["char_end"]
    if not parent.char_start <= a < b <= parent.char_end:
        raise ValueError("contextual_relevance_context_owner_mismatch")
    text = raw[a:b]
    header = raw[parent.char_start:parent.char_end].splitlines(keepends=True)[0] if parent.level else ""
    derived = {
        **source, "content": text, "display_text": text, "snippet": text,
        "char_start": a, "char_end": b,
        "byte_start": len(raw[:a].encode("utf-8")), "byte_end": len(raw[:b].encode("utf-8")),
        "line_start": span["line_start"], "line_end": span["line_end"],
        "title": parent.title, "heading_path": " > ".join(parent.heading_path),
        "_reference_evidence": {
            **source["_reference_evidence"], "char_start": a, "char_end": b, "text": text,
            "owner": {"text": header, "char_start": parent.char_start,
                      "char_end": parent.char_start + len(header),
                      "scope_start": parent.char_start, "scope_end": parent.char_end,
                      "logical_id": parent.logical_id} if parent.level else None,
        },
    }
    lineage = original_body_derivation_binding(
        question=question, body=text, candidate=derived, native_candidate=source)
    checked = _checked_original_candidate(
        question=question, evidence_text=text, candidate=derived,
        expected_project_identity=expected,
        lifecycle_intent=source.get("_lifecycle_intent", "current"))
    _, reason = prepare_reference_probe({}, candidate=derived, evidence_text=text)
    if (lineage is None or checked is None or reason is not None
            or not (checked[0].qualified or checked[0].reason == "source_valid_relevance_unassessed")):
        raise ValueError("contextual_relevance_context_recheck_failed:" + str(reason or
                         (checked[0].reason if checked else "missing_canonical_qualification")))
    return lineage


def _units(rows: list[dict], snapshot: dict, retrieval: dict, mode: str):
    from docmancer.core.structured_chunking import parse_markdown_parents
    from docmancer.docs.application.complete_context_scoring import ScoringUnit
    from docmancer.docs.domain.literal_context_admission import recheck_source_valid_candidate

    original = (retrieval.get("documentation_query_plan") or {}).get("original_question")
    if not isinstance(original, str) or not original.strip():
        raise ValueError("contextual_relevance_requires_original_question")
    units, observations = [], []
    documents: dict[str, tuple[str, list, list[tuple[int, ...]]]] = {}
    for row in rows:
        evidence_id = row.get("evidence_id")
        entry = snapshot.get(evidence_id)
        source = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, dict):
            raise ValueError("contextual_relevance_missing_checked_source")
        reference = source.get("_reference_evidence") or {}
        raw, seed_text = reference.get("raw_document"), reference.get("text")
        identity = reference.get("source") or {}
        if not isinstance(raw, str) or not isinstance(seed_text, str):
            raise ValueError("contextual_relevance_missing_checked_document")

        # This is the production pure canonical recheck. In particular it
        # requires the application-owned receipt of this exact live read; the
        # existence of raw_document or a qualified flag is not sufficient.
        rejection: dict = {}
        checked = recheck_source_valid_candidate(
            question=original, evidence_text=seed_text, candidate=source,
            expected_project_identity=retrieval.get("project_identity"),
            lifecycle_intent=source.get("_lifecycle_intent", "current"),
            rejection_diagnostics=rejection,
        )
        if checked is None:
            raise ValueError("contextual_relevance_source_recheck_failed:" + _canonical(rejection))
        if (row.get("path_or_url") != identity.get("canonical_path")
                or row.get("project_identity") != source.get("project_identity")):
            raise ValueError("contextual_relevance_public_source_mismatch")
        projected = entry.get("projected_source") or {}
        for key in ("evidence_id", "path_or_url", "snippet", "section", "content_sha256",
                    "version_binding", "project_identity", "authority", "scope", "line_start", "line_end"):
            if key in projected and projected[key] != row.get(key):
                raise ValueError("contextual_relevance_projected_row_mismatch:" + key)
        a, b = reference.get("char_start"), reference.get("char_end")
        body = row.get("snippet")
        if (type(a) is not int or type(b) is not int or not 0 <= a < b <= len(raw)
                or raw[a:b] != seed_text or not isinstance(body, str) or not body.strip()):
            raise ValueError("contextual_relevance_invalid_seed_span")
        start = raw.find(body, a, b)
        if start < 0 or raw.find(body, start + 1, b) >= 0:
            raise ValueError("contextual_relevance_ambiguous_row_span")
        end = start + len(body)
        if (row.get("line_start") != raw.count("\n", 0, start) + 1
                or row.get("line_end") != raw.count("\n", 0, end - 1) + 1):
            raise ValueError("contextual_relevance_row_line_mismatch")

        source_identity = _canonical({
            "source": identity, "member_binding": reference.get("member_binding"),
            "project_doc_content_hash": reference.get("project_doc_content_hash"),
            "authority": source.get("authority"),
            "instruction_trust": source.get("instruction_trust"),
        })
        cached = documents.get(source_identity)
        if cached is None:
            if _digest(raw) != identity.get("content_sha256"):
                raise ValueError("contextual_relevance_document_hash_mismatch")
            parents = parse_markdown_parents(raw, identity["document_id"])
            stack: list[int] = []
            ancestors: list[tuple[int, ...]] = []
            for index, parent in enumerate(parents):
                while stack and parents[stack[-1]].level >= parent.level:
                    stack.pop()
                prefix = (0,) if index and parents[0].level == 0 else ()
                ancestors.append((*prefix, *stack))
                if parent.level:
                    stack.append(index)
            cached = documents[source_identity] = (raw, parents, ancestors)
        elif cached[0] != raw:
            raise ValueError("contextual_relevance_inconsistent_document")
        _, parents, ancestors = cached
        owners = [i for i, parent in enumerate(parents)
                  if parent.char_start <= start < end <= parent.char_end]
        if len(owners) != 1:
            raise ValueError("contextual_relevance_ambiguous_owner")
        owner_index = owners[0]
        owner = parents[owner_index]
        spans = []
        for index in ancestors[owner_index]:
            ancestor = parents[index]
            # Parser parents end at the next heading. Therefore this includes
            # an ancestor's own introduction and header, never its descendants.
            spans.append(_span(raw, ancestor.char_start, ancestor.char_end, "ancestor_own_section"))
        if owner.level:
            header_end = owner.char_start + len(raw[owner.char_start:owner.char_end].splitlines(keepends=True)[0])
            # Do not duplicate a heading already present in the unchanged row.
            if header_end <= start:
                spans.append(_span(raw, owner.char_start, header_end, "own_heading"))
        applied = spans if mode == "contextual" else []
        for span in applied:
            span_owners = [parent for parent in parents
                           if parent.char_start <= span["char_start"] < span["char_end"] <= parent.char_end]
            if len(span_owners) != 1:
                raise ValueError("contextual_relevance_ambiguous_context_owner")
            span["native_derivation_sha256"] = _check_context_span(
                source, raw, span_owners[0], span, original, retrieval.get("project_identity"))
            span["source_recheck"] = "same_call_derivation_and_canonical_qualification"
        context = "".join(raw[span["char_start"]:span["char_end"]] for span in applied)
        units.append(ScoringUnit(evidence_id, body, context))
        observations.append({
            "evidence_id": evidence_id, "path": identity["canonical_path"],
            "source_identity_sha256": _digest(source_identity),
            "source_sha256": identity["content_sha256"],
            "heading_path": list(owner.heading_path),
            "body": _span(raw, start, end, "unchanged_checked_row"),
            "available_context_spans": spans, "context_spans": applied,
            "context_sha256": _digest(context), "context_utf8_bytes": len(context.encode("utf-8")),
            "source_recheck": "current_native_receipt_and_canonical_qualification",
        })
    return units, observations


@contextmanager
def installed_relevance(mode: str, observer: Callable[[dict], None] | None = None) -> Iterator[None]:
    """Temporarily install one evaluation control in a dedicated MCP worker.

    The caller sets DOCATLAS_EXPERIMENT_JOINT_RELEVANCE=mini and the prepared
    model path. ``observer`` receives independent diagnostic events and must
    never be used by selection. Both hooks and the request binding are restored
    on exit; ordinary MiniLM and the default product require no installation.
    """
    if mode not in MODES:
        raise ValueError("contextual_relevance_unknown_mode")
    if os.environ.get("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE") != "mini":
        raise ValueError("contextual_relevance_requires_joint_mini")
    from docmancer.docs.application import joint_context_selection as joint
    from docmancer.docs.application import experimental_selection_modes as semantic
    from docmancer.docs.application.complete_context_scoring import score_complete_units

    original_select = joint.select_joint_context
    original_score = semantic.score_joint_relevance
    original_settings = joint._continuation_settings

    def emit(receipt: dict) -> None:
        if observer is not None:
            try:
                observer(deepcopy({"event": "semantic_relevance", **receipt}))
            except Exception as exc:
                # A passive recorder is never allowed to change the ranking.
                receipt["observer_error"] = True
                receipt["diagnostics_status"] = "recorder_failed"
                try:
                    sys.stderr.write(_canonical({"event": "q6_semantic_observer_failed",
                                                 "error_type": type(exc).__name__}) + "\n")
                except Exception:
                    pass

    def select(payload, snapshot, retrieval, *args, **kwargs):
        token = _CALL.set((snapshot, retrieval))
        try:
            return original_select(payload, snapshot, retrieval, *args, **kwargs)
        finally:
            _CALL.reset(token)

    def settings():
        return {**original_settings(), "q6_evaluation_relevance": {"recipe": RECIPE, "mode": mode}}

    def score(queries, rows, model_path):
        receipt: dict = {
            "recipe": RECIPE, "mode": mode, "status": "scoring",
            "ranking_only": True, "model_pairs": 0, "model_forwards": 0,
            "model_input_tokens": 0, "rows": [], "lanes": {},
            "context_is_delivered_evidence": False,
            "diagnostics_status": "available_in_receipt",
        }
        try:
            call = _CALL.get()
            if call is None:
                raise ValueError("contextual_relevance_requires_live_selection_scope")
            snapshot, retrieval = call
            units, receipt["rows"] = _units(rows, snapshot, retrieval, mode)
            scores = {}
            for key, query in queries.items():
                scored, lane_receipt = score_complete_units(
                    (query["text"],), units, model_path,
                    fit_whole_pair=True, record_intervals=True,
                )
                if [item["identity"] for item in scored] != [unit.identity for unit in units]:
                    raise ValueError("contextual_relevance_score_identity_mismatch")
                values = [_sigmoid(item["score"]) for item in scored]
                scores[key] = values
                receipt["lanes"][key] = {"query": query["text"], "receipt": lane_receipt}
                for counter in ("model_pairs", "model_forwards", "model_input_tokens"):
                    receipt[counter] += lane_receipt[counter]
                for row_receipt, detail, value in zip(receipt["rows"], scored, values, strict=True):
                    row_receipt.setdefault("scores", {})[key] = {
                        **detail, "raw_logit": detail["score"], "score": value,
                    }
            receipt["status"] = "complete"
            emit(receipt)
            return scores, receipt
        except Exception as exc:
            receipt.update(status="error", error_type=type(exc).__name__, error=str(exc))
            if isinstance(exc, semantic.JointSemanticRelevanceError):
                receipt["failed_scorer_receipt"] = exc.receipt
                for counter in ("model_pairs", "model_forwards", "model_input_tokens"):
                    receipt[counter] += exc.receipt.get(counter, 0)
            emit(receipt)
            raise semantic.JointSemanticRelevanceError("Q6 relevance experiment failed: " + str(exc), receipt) from exc

    joint.select_joint_context = select
    semantic.score_joint_relevance = score
    joint._continuation_settings = settings
    try:
        yield
    finally:
        joint.select_joint_context = original_select
        semantic.score_joint_relevance = original_score
        joint._continuation_settings = original_settings
