"""Experimental paired native-selector relevance, disabled unless explicitly enabled.

NEW adapter recipe: exact checked row snippet is target.text; line coordinates
are native inclusive source lines, NOT full-document character offsets. Context
contains only an explicit allowlist of source identity/scope/heading/hash fields
already present on that checked row and its checked snapshot source. No document
read, retrieval, ancestors, incoming references, gold, or synthetic window.
This is NOT the scorer's calibrated own-body/full-document input contract. The
pinned scorer supplies model/prompt mechanics only; its old threshold and section
scores are deliberately not used. These scores rank default-eligible rows inside
the existing lexical MMR/cost/fitter, not pure top-k or semantic eligibility.

DOCATLAS_EXPERIMENT_PAIRED_QWEN=1 enables B. A leaves it unset.
DOCATLAS_EXPERIMENT_PAIRED_TRACE=/absolute/file.jsonl independently records A/B.
DOCATLAS_EXPERIMENT_PAIRED_CACHE=/absolute/directory optionally persists exact
input scores. Model assets use DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH and are
verified on EVERY call, even all-cache calls. Cache digests detect corruption,
not malicious modification. Trace files contain source text; protect accordingly.
"""
from __future__ import annotations

import hashlib
import gzip
import json
import math
import os
from pathlib import Path
import uuid


ADAPTER_RECIPE = {
    "id": "paired-default-checked-snippet-source-metadata-v1",
    "target": "exact checked row snippet; native inclusive line_start/line_end",
    "context": "allowlisted checked row and checked snapshot source metadata only",
    "no": ["extra retrieval", "full document", "gold", "old threshold", "old section scores"],
    "scope": "Qwen relevance + default lexical eligibility/MMR/cost/fitter; not pure top-k",
}
_CONTEXT_FIELDS = (
    "project_identity", "path_or_url", "scope", "authority", "version_binding",
    "section", "heading_path", "content_hash", "source_hash", "sha256",
    "_source_snapshot_sha256", "_source_catalog_hash", "generation_id",
    "source_class", "source_type", "doc_scope", "module_path", "version",
    "requested_version", "docs_snapshot_exact", "project_doc_catalog_entry_hash",
    "project_doc_content_hash",
)
ADAPTER_RECIPE["context_fields"] = list(_CONTEXT_FIELDS)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def enabled():
    return os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_QWEN") == "1"


def normalized(value):
    """Remove ONLY the two explicitly volatile fields, retaining all other data."""
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()
                if key not in {"evidence_id", "source_uri"}}
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    return value


class PoolTrace:
    """Independent opt-in JSONL sink; never attached to the priced packet.

    Compare ordered stage normalized_rows_sha256 and normalized_snapshots_sha256
    for identical original_question/budget/portion in A and B. Equality is NOT
    inferred merely from a matching query: callers must compare all three stages.
    Fail closed on requested trace I/O errors rather than silently omit evidence.
    """

    def __init__(self, retrieval, cap, limit, references, portion):
        self.path = os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_TRACE")
        self.base = {}
        if self.path:
            self.base = {
                "schema": "paired-native-checked-pool-v1", "run_id": uuid.uuid4().hex,
                "arm": "B" if enabled() else "A0",
                "scope": ADAPTER_RECIPE["scope"] if enabled() else "default native joint selector",
                "original_question": (retrieval.get("documentation_query_plan") or {}).get("original_question"),
                "budget": {"requested_cap": cap, "effective_limit": limit,
                           "max_source_references": references},
                "portion": portion,
                "volatile_fields_excluded": ["evidence_id", "source_uri"],
                "equality_claim": "compare all ordered raw_checked/post_prune/eligible stage digests across arms",
            }
            if os.environ.get("DOCATLAS_EXPERIMENT_QWEN_STUDY") == "1":
                self.base.update(
                    arm="step17_" + os.environ.get("DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE", "invalid"),
                    scope="separately flagged pipeline study; inspect qwen_study_settings before claiming paired equality",
                )

    def emit(self, event, **fields):
        if not self.path:
            return
        data = (canonical({**self.base, "event": event, **fields}) + "\n").encode("utf-8")
        # Independent gzip members preserve one atomic append per event even
        # with multiple worker processes. Decompression reproduces exact JSONL.
        if str(self.path).endswith('.gz'):
            data = gzip.compress(data, compresslevel=1, mtime=0)
        # One append per event. No model-visible diagnostics or stdout output.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            if os.write(fd, data) != len(data):
                raise OSError("paired_trace_short_write")
        finally:
            os.close(fd)

    def manifest(self, stage, rows, snapshot, **details):
        if not self.path:
            return
        bound = [snapshot[row["evidence_id"]] for row in rows]
        clean_rows, clean_bound = normalized(rows), normalized(bound)
        self.emit("pool_manifest", stage=stage, row_count=len(rows),
                  normalized_rows=clean_rows, normalized_snapshots=clean_bound,
                  normalized_rows_sha256=digest(clean_rows),
                  normalized_snapshots_sha256=digest(clean_bound),
                  raw_rows=rows, raw_snapshots=bound, **details)

    def decision(self, item, decision, score, **details):
        self.emit("selection_decision", group=item.group, indices=list(item.indices),
                  decision=decision, priority=list(score), cost_bytes=item.cost, **details)


class CheckedRowDocuments:
    """New document(id) adapter accepted by the pinned scoring entrypoint."""

    def __init__(self, rows, snapshot):
        self.documents = {}
        for index, row in enumerate(rows):
            source = snapshot[row["evidence_id"]]["source"]
            if not isinstance(row.get("snippet"), str):
                raise ValueError("paired_qwen_requires_checked_snippet")
            self.documents[str(index)] = {
                "adapter_recipe": ADAPTER_RECIPE,
                "target": {"text": row["snippet"], "line_start": row["line_start"],
                           "line_end": row["line_end"], "section": row.get("section")},
                "context": {
                    "checked_row": {key: row[key] for key in _CONTEXT_FIELDS if key in row},
                    "checked_source": {key: source[key] for key in _CONTEXT_FIELDS if key in source},
                },
            }

    def document(self, identity):
        return self.documents[identity]


def _score(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("paired_qwen_invalid_or_missing_score")
    return float(value)


def score_rows(retrieval, rows, snapshot, trace):
    """No lexical fallback. Fresh actual scorer receipt retained unmodified."""
    from . import context_evidence_scoring as scorer
    original = (retrieval.get("documentation_query_plan") or {}).get("original_question")
    if not isinstance(original, str) or not original.strip():
        raise ValueError("paired_qwen_requires_exact_original_question")
    model_path = os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", "")
    documents = CheckedRowDocuments(rows, snapshot)
    cache_path = os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_CACHE")
    contract = {"scorer_contract": scorer.CONTRACT, "adapter_recipe": ADAPTER_RECIPE,
                "calibration": "none; new inputs, ranking only"}
    values, keys, misses, cached_receipts = {}, {}, [], {}
    actual_receipt = None
    try:
        root = scorer.verify_assets(model_path)  # Also mandatory when every row is cached.
        if cache_path:
            cache = Path(cache_path)
            if not cache.is_absolute():
                raise ValueError("paired_cache_requires_absolute_directory")
            cache.mkdir(parents=True, exist_ok=True)
        for identity in documents.documents:
            key = digest({"query": original, "document": documents.document(identity), "contract": contract})
            keys[identity] = key
            path = cache / (key + ".json") if cache_path else None
            if path is not None and path.exists():
                entry = json.loads(path.read_text(encoding="utf-8"))
                if (entry["input_sha256"] != key or entry["receipt_sha256"] != digest(entry["scorer_receipt"])
                        or entry["scorer_receipt"].get("status") != "complete"
                        or entry["scorer_receipt"].get("contract_sha256") != scorer.CONTRACT_SHA256
                        or entry["entry_sha256"] != digest({k: v for k, v in entry.items() if k != "entry_sha256"})):
                    raise ValueError("paired_cache_digest_mismatch")
                values[identity] = _score(entry["score"])
                cached_receipts[key] = entry["scorer_receipt"]
            else:
                misses.append(identity)
        if misses:
            scored, actual_receipt = scorer.score_evidence_units(original, misses, documents, str(root))
            if actual_receipt.get("status") != "complete":
                raise ValueError("paired_qwen_incomplete_receipt")
            if len(scored) != len(misses) or {row["identity"] for row in scored} != set(misses):
                raise ValueError("paired_qwen_missing_or_duplicate_scores")
            for row in scored:
                identity = row["identity"]
                values[identity] = _score(row["score"])
            if cache_path:
                for identity in misses:
                    entry = {"input_sha256": keys[identity], "score": values[identity],
                             "scorer_receipt": actual_receipt, "receipt_sha256": digest(actual_receipt)}
                    entry["entry_sha256"] = digest(entry)
                    # Exclusive creation avoids replacing another process's completed entry.
                    try:
                        with (cache / (keys[identity] + ".json")).open("x", encoding="utf-8") as stream:
                            stream.write(canonical(entry))
                    except FileExistsError:
                        pass
        ordered = [values[str(index)] for index in range(len(rows))]
        trace.emit("qwen_scoring", adapter_recipe=ADAPTER_RECIPE,
                   scoring_contract_sha256=digest(contract), assets_verified=True,
                   cache_hits=len(rows) - len(misses), cache_misses=len(misses),
                   actual_scorer_receipt=actual_receipt,
                   actual_scorer_receipt_sha256=digest(actual_receipt) if actual_receipt is not None else None,
                   cached_scorer_receipts=cached_receipts, row_scores=ordered,
                   row_input_sha256=[keys[str(i)] for i in range(len(rows))])
        return ordered
    except Exception as exc:
        trace.emit("qwen_failure", error_type=type(exc).__name__, error=str(exc),
                   actual_scorer_receipt=getattr(exc, "receipt", actual_receipt),
                   cache_hits=len(values), cache_misses=len(misses), adapter_recipe=ADAPTER_RECIPE)
        raise
