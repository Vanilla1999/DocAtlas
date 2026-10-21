"""Observation-only local QA diagnostics; no model downloads during requests.

The readers tested in #216 and #218 failed semantic acceptance. Their predictions
cannot remove sources or grant answer authority. Automatic enforcement is not a
supported product mode; independent training/validation is tracked in #217.
"""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time

# Full RoBERTa reader, rather than the distilled reader that falsely refused
# nine useful V40 requests. The decoding policy and inputs remain unchanged.
MODEL_REPO = "onnx-community/roberta-base-squad2-ONNX"
MODEL_REVISION_PREFIX = "6d1aeed"
MODEL_NAMES = ("tokenizer.json", "onnx/model_quantized.onnx")
MAX_ROWS = 4096
MAX_CHARACTERS = 2_000_000
MAX_PAIRS = 8192
MAX_SECONDS = 60
MAX_QUERY_TOKENS = 64
MAX_SEQUENCE = 384
OVERLAP = 128
MAX_ANSWER_TOKENS = 30
_OBSERVER = ContextVar("docatlas_answerability_observer", default=None)
_LOCK = threading.Lock()
_ENGINE = None
_ENGINE_PATH = None


class AnswerabilityError(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def mode() -> str:
    value = os.environ.get("DOCATLAS_CONTEXT_ABSTENTION", "off")
    if value == "enforce":
        # A failed model is not an evidence veto. Never silently downgrade this
        # setting: the host must explicitly select off or diagnostic observation.
        raise AnswerabilityError("answerability_enforcement_not_validated")
    if value not in {"off", "observe"}:
        raise AnswerabilityError("answerability_invalid_config")
    return value


@contextmanager
def observe_answerability():
    receipts = []
    token = _OBSERVER.set(receipts)
    try:
        yield receipts
    finally:
        _OBSERVER.reset(token)


def _contexts(rows: list[dict], snapshot: dict) -> list[dict]:
    """Join only overlapping/adjacent checked spans of one source/section.

    Gaps remain separate inputs. No answer span can cross an invented separator.
    """
    if len(rows) > MAX_ROWS or sum(len(r["snippet"]) for r in rows) > MAX_CHARACTERS:
        raise AnswerabilityError("answerability_input_limit")
    groups = {}
    for row in rows:
        bound = snapshot.get(row["evidence_id"], {}).get("source", {})
        ref = bound.get("_reference_evidence") or {}
        raw, lo, hi = ref.get("raw_document"), ref.get("char_start"), ref.get("char_end")
        text = row["snippet"]
        if not isinstance(raw, str) or type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= len(raw):
            raise AnswerabilityError("answerability_source_binding")
        start = raw.find(text, lo, hi)
        if not text or start < 0 or raw.find(text, start + 1, hi) >= 0:
            raise AnswerabilityError("answerability_source_binding")
        key = json.dumps({"source": ref.get("source"), "snapshot": bound.get("_source_snapshot_sha256"),
                          "catalog": bound.get("_source_catalog_hash"), "generation": bound.get("generation_id"),
                          "module": bound.get("module_path"), "section": row.get("section"),
                          "scope": row.get("scope"), "version": row.get("version_binding"),
                          "authority": row.get("authority")}, sort_keys=True, ensure_ascii=False)
        group = groups.setdefault(key, {"raw": raw, "spans": []})
        if group["raw"] != raw:
            raise AnswerabilityError("answerability_source_binding")
        group["spans"].append((start, start + len(text), row["evidence_id"]))
    contexts = []
    for key, group in sorted(groups.items()):
        merged = []
        for lo, hi, evidence_id in sorted(group["spans"]):
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(hi, merged[-1][1])
                merged[-1][2].append(evidence_id)
            else:
                merged.append([lo, hi, [evidence_id]])
        for lo, hi, ids in merged:
            contexts.append({"text": group["raw"][lo:hi], "ids": ids,
                             "identity_sha256": hashlib.sha256(key.encode()).hexdigest(), "char_start": lo})
    return contexts


class _Reader:
    def __init__(self, directory: Path):
        try:
            manifest = json.loads((directory / "manifest.json").read_text())
            revision = manifest["revision"]
            if (manifest["repo"] != MODEL_REPO or len(revision) != 40
                    or not revision.startswith(MODEL_REVISION_PREFIX)
                    or set(manifest["files"]) != set(MODEL_NAMES)):
                raise ValueError("unexpected model manifest")
            verified = {}
            for name in MODEL_NAMES:
                path, expected = directory / name, manifest["files"][name]
                if path.is_symlink() or not path.is_file() or path.stat().st_size != expected["bytes"]:
                    raise ValueError("model size mismatch")
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != expected["sha256"]:
                    raise ValueError("model checksum mismatch")
                verified[name] = data
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise AnswerabilityError("answerability_model_unavailable_or_corrupt") from exc
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise AnswerabilityError("answerability_dependencies_unavailable") from exc
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(verified[MODEL_NAMES[1]], sess_options=options,
                                           providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_str(verified["tokenizer.json"].decode())
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.bos = self.tokenizer.token_to_id("<s>")
        self.eos = self.tokenizer.token_to_id("</s>")
        self.names = {i.name for i in self.session.get_inputs()}
        if self.bos is None or self.eos is None:
            raise AnswerabilityError("answerability_model_contract")
        self.manifest = manifest

    def assess(self, question: str, contexts: list[dict]) -> dict:
        import numpy as np
        query = self.tokenizer.encode(question, add_special_tokens=False).ids
        if not query or len(query) > MAX_QUERY_TOKENS:
            raise AnswerabilityError("answerability_query_limit")
        width = MAX_SEQUENCE - len(query) - 4
        begin, calls = time.monotonic(), 0
        best_margin, candidate, paired_tokens = -math.inf, None, 0
        for context in contexts:
            encoding = self.tokenizer.encode(context["text"], add_special_tokens=False)
            if not encoding.ids:
                raise AnswerabilityError("answerability_empty_tokenization")
            for offset in range(0, len(encoding.ids), width - OVERLAP):
                if calls >= MAX_PAIRS or time.monotonic() - begin > MAX_SECONDS:
                    raise AnswerabilityError("answerability_resource_limit")
                part = encoding.ids[offset:offset + width]
                ids = [self.bos] + query + [self.eos, self.eos] + part + [self.eos]
                feeds = {"input_ids": np.asarray([ids], dtype=np.int64),
                         "attention_mask": np.ones((1, len(ids)), dtype=np.int64)}
                output = self.session.run(None, {k: v for k, v in feeds.items() if k in self.names})
                if len(output) != 2:
                    raise AnswerabilityError("answerability_model_contract")
                start, end = (np.asarray(a).reshape(-1) for a in output)
                if len(start) != len(ids) or len(end) != len(ids) or not np.isfinite(start).all() or not np.isfinite(end).all():
                    raise AnswerabilityError("answerability_invalid_logits")
                null = float(start[0] + end[0])
                base = len(query) + 3
                # Standard extractive QA decision: best legal nonempty span vs
                # trained CLS/no-answer logit, threshold zero (not V40-calibrated).
                for i in range(len(part)):
                    j = i + int(np.argmax(end[base + i:base + min(len(part), i + MAX_ANSWER_TOKENS)]))
                    margin = float(start[base + i] + end[base + j]) - null
                    if margin > best_margin:
                        a, b = encoding.offsets[offset + i][0], encoding.offsets[offset + j][1]
                        best_margin = margin
                        candidate = {"source_ids": context["ids"], "identity_sha256": context["identity_sha256"],
                                     "char_start": context["char_start"] + a, "char_end": context["char_start"] + b}
                calls += 1
                paired_tokens += len(ids)
                if time.monotonic() - begin > MAX_SECONDS:
                    raise AnswerabilityError("answerability_resource_limit")
                if offset + width >= len(encoding.ids):
                    break
        if not calls:
            raise AnswerabilityError("answerability_empty_inputs")
        return {"decision": "no_answer" if best_margin < 0 else "candidate_answer",
                "best_span_minus_null": best_margin, "candidate": candidate,
                "pairs": calls, "pair_tokens": paired_tokens, "contexts": len(contexts),
                "seconds": time.monotonic() - begin, "scan_complete": True,
                "model_revision": self.manifest["revision"], "model_repo": MODEL_REPO}


def apply_answerability(payload: dict, snapshot: dict, retrieval: dict, question: str):
    setting = mode()
    if setting == "off" or payload.get("kind") != "docs_context" or not payload.get("sources"):
        return payload, snapshot
    if payload.get("requires_confirmation") or payload.get("hard_stop") or (payload.get("delivery_decision") or {}).get("deliverable") is False:
        return payload, snapshot
    from .model_visible_projection import validate_model_visible_projection
    from .experimental_candidate_selection import native_rank_selection_active
    if not native_rank_selection_active() or validate_model_visible_projection(payload, snapshot=snapshot):
        raise AnswerabilityError("answerability_requires_valid_native_sources")
    language = os.environ.get("DOCATLAS_ABSTENTION_LANGUAGE", "en")
    if language != "en":
        receipt = {"decision": "unknown", "reason": "unsupported_language", "scan_complete": False}
    else:
        contexts = _contexts(payload["sources"], snapshot)
        path = os.environ.get("DOCATLAS_ABSTENTION_MODEL_DIR", "")
        if not path or not Path(path).is_absolute():
            raise AnswerabilityError("answerability_model_unavailable_or_corrupt")
        directory = Path(path).resolve()
        global _ENGINE, _ENGINE_PATH
        if not _LOCK.acquire(timeout=MAX_SECONDS):
            raise AnswerabilityError("answerability_resource_limit")
        try:
            if _ENGINE is None or _ENGINE_PATH != directory:
                _ENGINE, _ENGINE_PATH = None, None
                _ENGINE = _Reader(directory)
                _ENGINE_PATH = directory
            receipt = _ENGINE.assess(question, contexts)
        finally:
            _LOCK.release()
    receipt.update(mode=setting, scope="acquired_source_context", corpus_absence_proven=False,
                   question_sha256=hashlib.sha256(question.encode()).hexdigest(),
                   pool_sha256=hashlib.sha256(json.dumps(payload["sources"], ensure_ascii=False, sort_keys=True).encode()).hexdigest())
    observed = _OBSERVER.get()
    if observed is not None:
        observed.append(deepcopy(receipt))
    retrieval.setdefault("retrieval_diagnostics", {})["answerability"] = deepcopy(receipt)
    # The receipt is host-only. Neither a QA span nor a null prediction is
    # sufficient to change the verified source payload or its authority.
    return payload, snapshot
