"""Opt-in CPU MiniLM-MaxP over complete *acquired* source sections.

Source checks are upstream and downstream. No new retrieval, remote inference,
semantic thresholds, source rewrites, or budget-driven removal of selected rows.
Default imports only the standard library. Model assets are provisioned explicitly.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time

MODE = "minilm-sections-v1"
LEGACY_FORMAT = "docatlas.sections.v1"
FORMAT = "docatlas.sections.v2"
# Positional wire contract: append only; never reorder or change these values.
# A set bit restores a field that was PRESENT with exactly this default. An
# unset bit never invents a field absent from the original envelope.
_ENVELOPE_DEFAULTS = (
    ("answer_supported", False),
    ("answer_available", False),
    ("edit_ready", False),
    ("requires_confirmation", False),
    ("hard_stop", False),
    ("covered_query_ids", []),
    ("missing_query_ids", []),
    ("missing_facets", []),
    ("read_next", []),
    ("missing", []),
    ("warnings", []),
)
_CONTEXT_MEANING = "Retrieved evidence only; not completeness or edit authority."
MODEL_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
MODEL_FILES = {
    "tokenizer.json": (711396, "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"),
    "onnx/model.onnx": (91011230, "5d3e70fd0c9ff14b9b5169a51e957b7a9c74897afd0a35ce4bd318150c1d4d4a"),
}
TOP_K = 5
MAX_INPUT_CHARS = 2_000_000
MAX_ROWS = 4096
MAX_PAIRS = 8192
MAX_SECONDS = 60
OUTPUT_LIMIT = 12000


class SectionCompressionError(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def enabled() -> bool:
    # If a trusted host explicitly provisioned a MiniLM model directory, use
    # the new efficient selection without requiring a second opt-in switch.
    # No model path -> no network, download, or surprise inference.
    setting = os.environ.get("DOCATLAS_CONTEXT_COMPRESSION")
    if setting is None:
        setting = MODE if os.environ.get("DOCATLAS_MINILM_MODEL_DIR") else "off"
    if setting not in ("", "off", MODE):
        raise SectionCompressionError("section_compression_invalid_config")
    return setting == MODE


_OBSERVER = ContextVar("docatlas_section_compression_observer", default=None)


@contextmanager
def observe_section_compression():
    """Collect per-request diagnostics, not source authority or mutable operands."""
    receipts = []
    token = _OBSERVER.set(receipts)
    try:
        yield receipts
    finally:
        _OBSERVER.reset(token)


@dataclass
class _Section:
    key: tuple
    rows: list[dict]
    text: str


def selection_limit() -> int:
    """Explicit host cap, not a learned sufficiency/absence threshold."""
    value = os.environ.get("DOCATLAS_SECTION_TOP_K", str(TOP_K))
    if value not in {"1", "2", "3", "5"}:
        raise SectionCompressionError("section_compression_invalid_top_k")
    return int(value)


def selection_units() -> str:
    # Facet ranking needs actual Markdown owner groupings; explicit fixed-k
    # rollback keeps the legacy grouping rather than inheriting the new mode.
    policy = os.environ.get("DOCATLAS_SECTION_SELECTION", "facet-guarded-v1")
    default = "markdown-owner-v1" if (policy.startswith("facet-") or policy.startswith("semantic-")) else "legacy"
    value = os.environ.get("DOCATLAS_SECTION_UNITS", default)
    if value not in {"legacy", "markdown-owner-v1"}:
        raise SectionCompressionError("section_compression_invalid_units")
    return value


def _adaptive_cutoff(sorted_scores: list[float], *, buffer: int = 0) -> tuple[int, dict]:
    """Choose k from all scored sections, without a hard-coded group ceiling.

    The 90%-window raw-logit gap is an experimental ranking signal, NOT
    evidence that the returned text suffices to answer the original question.
    A flat set has no distinguishing gap, so it proposes all admitted groups.
    A separate complete-packet token budget still applies.
    """
    count = len(sorted_scores)
    if not count:
        raise SectionCompressionError("section_compression_empty_scores")
    if (not all(math.isfinite(s) for s in sorted_scores)
            or any(a < b for a, b in zip(sorted_scores, sorted_scores[1:]))):
        raise SectionCompressionError("section_compression_invalid_score")
    if count == 1:
        return 1, {"gap_count": 0, "cutoff_rank": 1, "reason": "single_candidate", "buffer": buffer}
    gap_count = min(count - 1, (9 * count + 9) // 10)
    gaps = [sorted_scores[i] - sorted_scores[i + 1] for i in range(gap_count)]
    position = max(range(gap_count), key=lambda i: gaps[i])
    largest = gaps[position]
    if not math.isfinite(largest):
        raise SectionCompressionError("section_compression_invalid_score")
    if largest == 0:
        return count, {"gap_count": gap_count, "cutoff_rank": count,
                       "largest_gap": 0.0, "reason": "flat_scores_keep_all", "buffer": buffer}
    cutoff = position + 1
    return min(count, cutoff + buffer), {
        "gap_count": gap_count, "cutoff_rank": cutoff, "largest_gap": largest,
        "reason": "largest_gap", "buffer": buffer,
    }


def _sections(rows: list[dict], snapshot: dict) -> list[_Section]:
    """Group checked occurrences, retaining gaps and never fetching a neighbor."""
    if len(rows) > MAX_ROWS or sum(len(r["snippet"]) for r in rows) > MAX_INPUT_CHARS:
        raise SectionCompressionError("section_compression_input_limit")
    groups = {}
    for row in rows:
        bound = snapshot.get(row["evidence_id"], {}).get("source", {})
        ref = bound.get("_reference_evidence") or {}
        raw = ref.get("raw_document")
        start, end = ref.get("char_start"), ref.get("char_end")
        text = row["snippet"]
        if (not isinstance(raw, str) or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(raw) or not text):
            raise SectionCompressionError("section_compression_source_binding")
        pos = raw.find(text, start, end)
        if pos < 0 or raw.find(text, pos + 1, end) >= 0:
            raise SectionCompressionError("section_compression_source_binding")
        # Full native identity prevents merging namespaces, snapshots, or modules.
        identity = json.dumps({
            "source": ref.get("source"),
            "snapshot": bound.get("_source_snapshot_sha256"),
            "catalog": bound.get("_source_catalog_hash"),
            "generation": bound.get("generation_id"),
            "module": bound.get("module_path"),
        }, sort_keys=True, ensure_ascii=False)
        key = tuple(str(row.get(k) or "") for k in (
            "path_or_url", "section", "project_identity", "scope", "version_binding", "authority",
        )) + (identity,)
        group = groups.setdefault(key, {"raw": raw, "spans": [], "rows": []})
        if group["raw"] != raw:
            raise SectionCompressionError("section_compression_source_binding")
        group["spans"].append((pos, pos + len(text)))
        group["rows"].append(row)
    result = []
    for key, group in sorted(groups.items()):
        spans = []
        for a, b in sorted(group["spans"]):
            if spans and a <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
        text = "\n\n".join(group["raw"][a:b] for a, b in spans)
        result.append(_Section(key, group["rows"], text))
    if selection_units() == "markdown-owner-v1":
        return _attach_owned_headings(result, groups)
    return result


def _attach_owned_headings(sections: list[_Section], groups: dict) -> list[_Section]:
    """Only parsed empty heading ancestors join already-acquired descendants.

    Not a short-text or keyword filter. Orphan headings stay independent.
    No unacquired span is fetched, inferred or delivered. All selected original
    rows remain intact; shared ancestry is emitted only once by evidence ID.
    """
    from docmancer.core.structured_chunking import parse_markdown_parents
    structures, owners = {}, {}
    for i, section in enumerate(sections):
        source_key = (section.key[0], *section.key[2:])
        raw = groups[section.key]["raw"]
        if source_key not in structures:
            structures[source_key] = parse_markdown_parents(raw, json.dumps(source_key, ensure_ascii=False))
        spans = groups[section.key]["spans"]
        found = [p for p in structures[source_key]
                 if all(p.char_start <= a < b <= p.char_end for a, b in spans)]
        if len(found) == 1:
            owners[i] = found[0]
    parents_for = {i: [] for i in range(len(sections))}
    attached = set()
    for i, parent in owners.items():
        raw = groups[sections[i].key]["raw"]
        body = raw[parent.char_start:parent.char_end].splitlines(keepends=True)
        if not parent.level or not body or "".join(body[1:]).strip():
            continue
        stop = next((p.char_start for p in structures[(sections[i].key[0], *sections[i].key[2:])]
                     if p.char_start > parent.char_start and p.level <= parent.level), len(raw))
        for j, child in owners.items():
            if (i != j and (sections[i].key[0], *sections[i].key[2:]) == (sections[j].key[0], *sections[j].key[2:])
                    and parent.char_end <= child.char_start < stop and child.level > parent.level):
                child_body = raw[child.char_start:child.char_end].splitlines(keepends=True)
                if "".join(child_body[1:]).strip():
                    parents_for[j].append(i)
                    attached.add(i)
    result = []
    for i, section in enumerate(sections):
        if i in attached:
            continue
        ids, spans, rows = set(), [], []
        for j in [*parents_for[i], i]:
            group = groups[sections[j].key]
            spans.extend(group["spans"])
            for row in group["rows"]:
                if row["evidence_id"] not in ids:
                    ids.add(row["evidence_id"])
                    rows.append(row)
        merged = []
        for a, b in sorted(spans):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        raw = groups[section.key]["raw"]
        result.append(_Section(section.key, rows, "\n\n".join(raw[a:b] for a, b in merged)))
    return result


class _MiniLM:
    def __init__(self, directory: Path):
        # Verify bytes before constructing either backend; no remote code is loaded.
        blobs = {}
        for name, (size, digest) in MODEL_FILES.items():
            path = directory / name
            try:
                if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
                    raise OSError("missing or wrong-size model asset")
                data = path.read_bytes()
            except OSError as exc:
                raise SectionCompressionError("section_compression_model_unavailable") from exc
            if hashlib.sha256(data).hexdigest() != digest:
                raise SectionCompressionError("section_compression_model_integrity")
            blobs[name] = data
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise SectionCompressionError("section_compression_dependencies_unavailable") from exc
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            blobs["onnx/model.onnx"], sess_options=options, providers=["CPUExecutionProvider"],
        )
        self.tokenizer = Tokenizer.from_str(blobs["tokenizer.json"].decode("utf-8"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.cls = self.tokenizer.token_to_id("[CLS]")
        self.sep = self.tokenizer.token_to_id("[SEP]")
        if self.cls is None or self.sep is None:
            raise SectionCompressionError("section_compression_model_integrity")
        self.inputs = {entry.name for entry in self.session.get_inputs()}

    def score(self, question: str, sections: list[_Section], *, budget: dict | None = None,
              max_pairs: int = MAX_PAIRS, max_seconds: float = MAX_SECONDS) -> tuple[list[float], dict]:
        import numpy as np
        query = self.tokenizer.encode(question, add_special_tokens=False).ids
        if len(query) > 128:
            raise SectionCompressionError("section_compression_query_limit")
        width = 512 - len(query) - 3
        started = time.monotonic()
        if budget is None:
            budget = {"started": started, "pairs": 0}
        scores, calls, tokens = [], 0, 0
        for section in sections:
            passage = self.tokenizer.encode(section.text, add_special_tokens=False).ids
            best = -math.inf
            for offset in range(0, max(len(passage), 1), width):
                if budget["pairs"] >= min(MAX_PAIRS, max_pairs) or time.monotonic() - budget["started"] > min(MAX_SECONDS, max_seconds):
                    raise SectionCompressionError("section_compression_resource_limit")
                part = passage[offset:offset + width]
                ids = [self.cls] + query + [self.sep] + part + [self.sep]
                types = [0] * (len(query) + 2) + [1] * (len(part) + 1)
                feeds = {
                    "input_ids": np.asarray([ids], dtype=np.int64),
                    "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
                    "token_type_ids": np.asarray([types], dtype=np.int64),
                }
                value = float(self.session.run(None, {k: v for k, v in feeds.items()
                                                      if k in self.inputs})[0].reshape(-1)[0])
                if not math.isfinite(value):
                    raise SectionCompressionError("section_compression_invalid_score")
                best = max(best, value)
                calls += 1
                budget["pairs"] += 1
                tokens += len(ids)
            scores.append(best)
        return scores, {"forward_passes": calls, "input_pair_tokens": tokens,
                        "truncated_tokens": 0, "scoring_seconds": time.monotonic() - started}


_LOCK = threading.Lock()
_ENGINE = None
_ENGINE_PATH = None


def select_sections(payload: dict, snapshot: dict, retrieval: dict, question: str):
    """Select original whole sections with an uncapped Adaptive-k decision.

    There is no arbitrary Adaptive-k five-section ceiling. If the selected
    prefix exceeds the existing 12k *full machine packet* budget, deliver the
    longest affordable whole-section prefix with an explicit truncated status
    and diagnostic, never with proof of answer completeness.
    """
    rows = payload.get("sources") or []
    if not enabled() or payload.get("kind") != "docs_context" or not rows:
        return payload, snapshot
    if (payload.get("requires_confirmation") or payload.get("hard_stop")
            or (payload.get("delivery_decision") or {}).get("deliverable") is False):
        return payload, snapshot
    from .experimental_candidate_selection import native_rank_selection_active
    if not native_rank_selection_active():
        raise SectionCompressionError("section_compression_requires_native_read")
    policy = os.environ.get("DOCATLAS_SECTION_SELECTION", "facet-guarded-v1")
    from .facet_selection import POLICIES as FACET_POLICIES
    from .semantic_local_sufficiency import POLICIES as SEMANTIC_POLICIES
    from .coverage_selection import POLICIES as EXPERIMENT_POLICIES, select_coverage_sections
    if policy in EXPERIMENT_POLICIES and policy not in FACET_POLICIES:
        return select_coverage_sections(payload, snapshot, retrieval, question, policy)
    if policy not in {"fixed", "adaptive-gap-v1", "adaptive-gap-b1-v1"} | FACET_POLICIES | SEMANTIC_POLICIES:
        raise SectionCompressionError("section_compression_invalid_selection_policy")
    fixed_limit = selection_limit() if policy == "fixed" else None
    effective_policy = "facet-guarded-v1" if policy in SEMANTIC_POLICIES else policy
    units = selection_units()
    sections = _sections(rows, snapshot)
    configured = os.environ.get("DOCATLAS_MINILM_MODEL_DIR", "")
    if not configured or not Path(configured).is_absolute():
        raise SectionCompressionError("section_compression_model_unavailable")
    directory = Path(configured).resolve()
    global _ENGINE, _ENGINE_PATH
    with _LOCK:
        if _ENGINE is None or _ENGINE_PATH != directory:
            _ENGINE = None
            _ENGINE_PATH = None
            _ENGINE = _MiniLM(directory)
            _ENGINE_PATH = directory
        budget = {"started": time.monotonic(), "pairs": 0}
        scores, receipt = _ENGINE.score(question, sections, budget=budget)
        if effective_policy in FACET_POLICIES:
            from .facet_selection import plan
            facet_order, facet_count = plan(
                _ENGINE, question, sections, scores, receipt,
                policy=effective_policy, snapshot=snapshot, budget=budget,
            )
    ranking = sorted(range(len(sections)), key=lambda i: (-scores[i], sections[i].key))
    if policy == "fixed":
        requested_k = min(fixed_limit, len(sections))
    elif effective_policy in FACET_POLICIES:
        ranking, requested_k = facet_order, facet_count
    else:
        requested_k, cutoff = _adaptive_cutoff(
            [scores[i] for i in ranking],
            buffer=1 if policy == "adaptive-gap-b1-v1" else 0,
        )
        receipt["adaptive_cutoff"] = cutoff
    if policy in SEMANTIC_POLICIES:
        from .semantic_local_sufficiency import review
        ranking, requested_k, semantic_receipt = review(
            question, rows, sections, snapshot, ranking, requested_k, policy)
        receipt["semantic_sufficiency"] = semantic_receipt
    from .experimental_context_finalization import _rebuild, _refresh_estimate

    def project(prefix_k: int):
        selected = {r["evidence_id"] for i in ranking[:prefix_k] for r in sections[i].rows}
        retained = [r for r in rows if r["evidence_id"] in selected]
        limited = prefix_k < requested_k
        result, bindings = _rebuild(
            payload, snapshot, retrieval, retained,
            reason="budget_limited" if limited else "section_selection",
        )
        if limited:
            result["status"] = "truncated"
            result["source_selection"] = {
                "candidate_rows": len(rows),
                "selected_rows": len(retained),
                "omitted_rows": len(rows) - len(retained),
                "scope": "admitted_candidates",
                "budget_limited": True,
            }
            _refresh_estimate(result)
        if [r["evidence_id"] for r in result["sources"]] != [r["evidence_id"] for r in retained]:
            raise SectionCompressionError("section_compression_identity_mismatch")
        return result, bindings, retained

    if policy == "fixed":
        top_k = requested_k
        result, bindings, retained = project(top_k)
    else:
        # Price the negotiated v1/v2 *complete* packet, not just its snippets.
        # All trials reuse the same MiniLM scores. Non-budget errors propagate.
        def fits(prefix_k: int):
            candidate = project(prefix_k)
            try:
                encode_sections(candidate[0])
            except SectionCompressionError as exc:
                if exc.reason_code == "section_compression_output_limit":
                    return None
                raise
            return candidate

        top_k, selected_result = requested_k, fits(requested_k)
        if selected_result is None:
            low, high = 1, requested_k - 1
            top_k = 0
            while low <= high:
                middle = (low + high) // 2
                trial = fits(middle)
                if trial is None:
                    high = middle - 1
                else:
                    top_k, selected_result = middle, trial
                    low = middle + 1
            if selected_result is None:
                # One section is too large: fail explicitly, no invented answer.
                raise SectionCompressionError("section_compression_output_limit")
        result, bindings, retained = selected_result
        receipt["adaptive_cutoff"].update(
            requested_sections=requested_k, selected_after_budget=top_k,
            budget_limited=top_k < requested_k, budget_limit_tokens=OUTPUT_LIMIT,
        )
    receipt.update(
        method=MODE, model_revision=MODEL_REVISION,
        selection_policy=policy, configured_top_k=fixed_limit,
        scoring_question_sha256=hashlib.sha256(question.encode()).hexdigest(),
        candidate_rows=len(rows), candidate_sections=len(sections),
        selected_rows=len(retained), selected_sections=top_k, top_k=top_k,
        units=units, selected_evidence_ids=[r["evidence_id"] for r in retained],
    )
    if policy in SEMANTIC_POLICIES:
        receipt["semantic_sufficiency"]["delivered_groups"] = top_k
        receipt["semantic_sufficiency"]["budget_limited"] = top_k < requested_k
        receipt["semantic_sufficiency"]["final_semantic_completeness"] = "unverified"
    retrieval.setdefault("retrieval_diagnostics", {})["section_compression"] = deepcopy(receipt)
    observed = _OBSERVER.get()
    if observed is not None:
        detail = deepcopy(receipt)
        detail["ranked_sections"] = [
            {"rank": rank, "score": scores[index], "selected": rank <= top_k,
             "rank_meaning": "selection_priority" if effective_policy in FACET_POLICIES else "global_score",
             "path": sections[index].rows[0].get("path_or_url"),
             "section": sections[index].rows[0].get("section"),
             "scoring_text_sha256": hashlib.sha256(sections[index].text.encode()).hexdigest(),
             "evidence_ids": [r["evidence_id"] for r in sections[index].rows]}
            for rank, index in enumerate(ranking, 1)
        ]
        observed.append(detail)
    return result, bindings


def _common(rows: list[dict]) -> dict:
    return {k: deepcopy(v) for k, v in rows[0].items()
            if k not in {"snippet", "evidence_id", "source_uri", "line_start", "line_end"}
            and all(k in row and row[k] == v for row in rows[1:])}


def encode_sections(payload: dict, *, context_format: str | None = None) -> dict:
    """Use safe v1 by default; explicit adaptive v2 chooses the cheapest packet.

    FORMAT requests adaptive v2 with v1 fallback, not a forced wire version.
    LEGACY_FORMAT requests only v1 for backwards-compatible callers.
    """
    if context_format is None:
        setting = os.environ.get("DOCATLAS_SECTION_WIRE_FORMAT", "v1")
        if setting not in {"v1", "adaptive-v2"}:
            raise SectionCompressionError("section_compression_unknown_format")
        context_format = LEGACY_FORMAT if setting == "v1" else FORMAT
    if context_format not in (LEGACY_FORMAT, FORMAT):
        raise SectionCompressionError("section_compression_unknown_format")
    if payload.get("kind") != "docs_context" or not payload.get("sources"):
        return payload
    if context_format == FORMAT and (
        payload.get("requires_confirmation") or payload.get("hard_stop")
        or payload.get("status") == "confirmation_required"
        or (payload.get("delivery_decision") or {}).get("deliverable") is False
    ):
        return payload
    candidates = [_encode_section_candidate(payload, context_format=LEGACY_FORMAT)]
    if context_format == FORMAT:
        candidates.extend(
            _encode_section_candidate(payload, context_format=FORMAT, group_by=group_by)
            for group_by in ("path", "section")
        )
    # All candidates include their own fixed-point estimate. Price the actual
    # complete JSON, never an approximation of just the source rows.
    result = min(candidates, key=lambda candidate: (
        candidate["estimated_tokens"],
        len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
        candidate["context_format"] != FORMAT,
    ))
    if result["estimated_tokens"] > OUTPUT_LIMIT:
        raise SectionCompressionError("section_compression_output_limit")
    return result


def _encode_section_candidate(payload: dict, *, context_format: str, group_by: str = "section") -> dict:
    """Versioned lossless factoring, not a second semantic compression pass.

    Every selected source field and exact string is retained. Existing source_uri
    values remain continuation capabilities, NOT new provenance/read grants.
    """
    if context_format not in (LEGACY_FORMAT, FORMAT):
        raise SectionCompressionError("section_compression_unknown_format")
    if payload.get("kind") != "docs_context" or not payload.get("sources"):
        return payload
    if context_format == FORMAT and (
        payload.get("requires_confirmation") or payload.get("hard_stop")
        or (payload.get("delivery_decision") or {}).get("deliverable") is False
        or payload.get("status") == "confirmation_required"
    ):
        return payload
    from .projection_tokenizer import projection_token_count
    rows = payload["sources"]
    groups = {}
    for ordinal, row in enumerate(rows):
        if group_by == "section":
            key = tuple(str(row.get(k) or "") for k in (
                "path_or_url", "section", "project_identity", "scope", "version_binding", "authority",
            ))
        else:
            # Factoring is not semantic merging: differing section, scope,
            # version and authority remain explicit per fragment when needed.
            key = json.dumps(row.get("path_or_url"), ensure_ascii=False, sort_keys=True)
        groups.setdefault(key, []).append((ordinal, row))
    result = {k: deepcopy(v) for k, v in payload.items() if k != "sources"}
    if any(k in result for k in ("context_format", "source_defaults", "source_groups", "source_estimated_tokens",
                               "envelope_defaults", "context_meaning")):
        raise SectionCompressionError("section_compression_format_collision")
    result["context_format"] = context_format
    if context_format == FORMAT:
        mask = 0
        for bit, (name, default) in enumerate(_ENVELOPE_DEFAULTS):
            if name in result and type(result[name]) is type(default) and result[name] == default:
                del result[name]
                mask |= 1 << bit
        if mask:
            result["envelope_defaults"] = mask
        result["context_meaning"] = _CONTEXT_MEANING
    result["source_defaults"] = _common(rows)
    result["source_groups"] = []
    for key, group in sorted(groups.items()):
        common = {k: v for k, v in _common([r for _, r in group]).items()
                  if k not in result["source_defaults"]}
        fragments = [{"index": ordinal, "fields": {k: deepcopy(v) for k, v in row.items()
                      if k not in common and k not in result["source_defaults"]}}
                     for ordinal, row in group]
        result["source_groups"].append({"common": common, "fragments": fragments})
    result["source_estimated_tokens"] = result.get("estimated_tokens")
    for _ in range(8):
        wire = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        cost = max(projection_token_count(wire), math.ceil(len(wire) / 4))
        if result.get("estimated_tokens") == cost:
            break
        result["estimated_tokens"] = cost
    else:
        raise SectionCompressionError("section_compression_budget_estimate")
    if expand_sections(result) != payload:
        raise SectionCompressionError("section_compression_roundtrip")
    return result


def expand_sections(payload: dict) -> dict:
    """Decode v1/v2 losslessly. Decoding does not authorize any source.

    V2 envelope_defaults is a presence bitmap over _ENVELOPE_DEFAULTS;
    omitted false flags remain false, not permission/completeness grants.
    """
    context_format = payload.get("context_format")
    if context_format not in (LEGACY_FORMAT, FORMAT):
        return deepcopy(payload)
    reserved = {"context_format", "source_defaults", "source_groups", "source_estimated_tokens"}
    if context_format == FORMAT:
        reserved.update(("envelope_defaults", "context_meaning"))
    result = {k: deepcopy(v) for k, v in payload.items()
              if k not in reserved}
    if context_format == FORMAT:
        mask = payload.get("envelope_defaults", 0)
        if (type(mask) is not int or not 0 <= mask < (1 << len(_ENVELOPE_DEFAULTS))
                or payload.get("context_meaning") != _CONTEXT_MEANING):
            raise ValueError("invalid compact envelope defaults")
        for bit, (name, default) in enumerate(_ENVELOPE_DEFAULTS):
            if mask & (1 << bit):
                if name in result:
                    raise ValueError("overlapping envelope defaults")
                result[name] = deepcopy(default)
    sources = {}
    defaults = payload["source_defaults"]
    for group in payload["source_groups"]:
        common = group["common"]
        if set(common) & set(defaults):
            raise ValueError("overlapping source defaults")
        for fragment in group["fragments"]:
            i, fields = fragment["index"], fragment["fields"]
            if (type(i) is not int or i < 0 or i in sources
                    or set(fields) & (set(defaults) | set(common))):
                raise ValueError("invalid section source entry")
            sources[i] = {**deepcopy(defaults), **deepcopy(common), **deepcopy(fields)}
    if sorted(sources) != list(range(len(sources))):
        raise ValueError("noncontiguous source ordering")
    result["sources"] = [sources[i] for i in range(len(sources))]
    if payload["source_estimated_tokens"] is None:
        result.pop("estimated_tokens", None)
    else:
        result["estimated_tokens"] = payload["source_estimated_tokens"]
    return result
