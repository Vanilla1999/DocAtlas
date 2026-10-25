"""Experimental statement-preservation checks, NOT a question sufficiency oracle.

Compare exact source-coordinate coverage with an independently trained local NLI
classifier. Source statements (not questions) are NLI hypotheses. No gold labels,
new retrieval, generated text, authorization change or paid model call occurs.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import threading

from .semantic_budget import Budget, Exhausted

MODEL_REPO = "cross-encoder/nli-MiniLM2-L6-H768"
MODEL_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"
MODEL_NAME = "onnx/model_quint8_avx2.onnx"
MODEL_SHA256 = "44391a5241a62e0083c1a8899a71e69a092b95aea5ba89e14062925468eceac7"
FILES = ("tokenizer.json", "config.json", MODEL_NAME)
# Frozen conservative experiment settings, not calibrated truth probabilities.
MIN_ENTAILMENT = 0.995
MAX_CONTRADICTION = 0.001
MAX_SECONDS = 12
MAX_PAIRS = 96
MAX_REMOVAL_TRIALS = 8
_LOCK = threading.Lock()
_ENGINE = None
_ENGINE_PATH = None


def _error(code):
    from .section_compression import SectionCompressionError
    return SectionCompressionError("semantic_preservation_" + code)


class NLI:
    def __init__(self, directory):
        try:
            manifest = json.loads((directory / "manifest.json").read_text())
            if (manifest["repo"] != MODEL_REPO or manifest["revision"] != MODEL_REVISION
                    or set(manifest["files"]) != set(FILES)):
                raise ValueError("unrecognized manifest")
            assets = {}
            for name in FILES:
                path = directory / name
                meta = manifest["files"][name]
                if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 400_000_000:
                    raise ValueError("invalid asset")
                raw = path.read_bytes()
                if len(raw) != meta["bytes"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                    raise ValueError("asset hash mismatch")
                assets[name] = raw
            if hashlib.sha256(assets[MODEL_NAME]).hexdigest() != MODEL_SHA256:
                raise ValueError("unexpected model weights")
            if json.loads(assets["config.json"])["id2label"] != {"0": "contradiction", "1": "entailment", "2": "neutral"}:
                raise ValueError("unrecognized class mapping")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise _error("invalid_model") from exc
        import onnxruntime as ort
        from tokenizers import Tokenizer
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(assets[MODEL_NAME], sess_options=options, providers=["CPUExecutionProvider"])
        self.names = {i.name for i in self.session.get_inputs()}
        self.tokenizer = Tokenizer.from_str(assets["tokenizer.json"].decode())
        self.tokenizer.no_truncation(); self.tokenizer.no_padding()

    def classify(self, premise, hypothesis, budget, cache):
        import numpy as np
        key = (premise, hypothesis)
        if key in cache:
            budget.cache_hits += 1
            return cache[key]
        enc = self.tokenizer.encode(premise, hypothesis, add_special_tokens=True)
        if len(enc.ids) > 512:
            return None  # no silent truncation or incomplete-premise entailment
        budget.take(len(enc.ids))
        feeds = {"input_ids": np.asarray([enc.ids], dtype=np.int64),
                 "attention_mask": np.ones((1, len(enc.ids)), dtype=np.int64),
                 "token_type_ids": np.asarray([enc.type_ids], dtype=np.int64)}
        logits = np.asarray(self.session.run(None, {k: v for k, v in feeds.items() if k in self.names})[0]).reshape(-1)
        if budget.elapsed() >= budget.seconds:
            raise Exhausted("request_deadline")
        if len(logits) != 3 or not np.isfinite(logits).all():
            raise _error("invalid_logits")
        probabilities = np.exp(logits - np.max(logits)); probabilities /= probabilities.sum()
        value = tuple(float(x) for x in probabilities)
        cache[key] = value
        return value


def _identity(section):
    # Same native source identity, project, snapshot, scope, version and authority.
    return (section.key[0], *section.key[2:])


def _guard_terms(text):
    pattern = r"`[^`]+`|\b\d+(?:[.,]\d+)?\b|\b(?:not|never|unless|without|only|before|after|if|except|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b"
    return Counter(re.findall(pattern, text.casefold()))


def _statements(section):
    text = section.text
    if "```" in text or "~~~" in text or re.search(r"[\u0400-\u04ff]", text) or "|" in text:
        return None  # code/tables/unsupported language stay intact
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    parts = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", body) if p.strip()]
    if not parts or len(parts) > 12:
        return None
    return [(f"Section: {section.key[1]}\n{p}", p) for p in parts]


def _exactly_covered(before, after):
    """A mathematical span-union test, not a semantic model judgment."""
    for item in before:
        lo, hi = item["char_start"], item["char_start"] + len(item["text"])
        intervals = sorted((x["char_start"], x["char_start"] + len(x["text"])) for x in after
                           if x["identity_sha256"] == item["identity_sha256"])
        cursor = lo
        for left, right in intervals:
            if left > cursor:
                break
            if right > cursor:
                cursor = right
            if cursor >= hi:
                break
        if cursor < hi:
            return False
    return True


def review(question, rows, sections, snapshot, ranking, count, policy):
    from .answerability import _contexts
    original = list(ranking[:count]); chosen = list(original)
    budget = Budget(MAX_SECONDS, MAX_PAIRS)
    cache, decisions, protected = {}, [], set()
    use_nli = policy == "semantic-nli-prune-v1"
    def contexts(indices):
        ids = {r["evidence_id"] for i in indices for r in sections[i].rows}
        return _contexts([r for r in rows if r["evidence_id"] in ids], snapshot)
    # Exact removal is separately certified for every original source interval.
    for i in list(reversed(chosen))[:128]:
        if budget.elapsed() >= MAX_SECONDS:
            break
        trial = [j for j in chosen if j != i]
        if trial and _exactly_covered(contexts([i]), contexts(trial)):
            chosen = trial
            decisions.append({"section": i, "reason": "exact_source_span_covered"})
    exact_chosen = list(chosen)
    limited = False; checked = 0
    if use_nli:
        configured = os.environ.get("DOCATLAS_NLI_MODEL_DIR") or os.environ.get("DOCATLAS_SUFFICIENCY_MODEL_DIR", "")
        if not configured or not Path(configured).is_absolute():
            raise _error("model_unavailable")
        directory = Path(configured).resolve()
        if not _LOCK.acquire(timeout=MAX_SECONDS):
            raise _error("resource_limit")
        global _ENGINE, _ENGINE_PATH
        try:
            if _ENGINE is None or _ENGINE_PATH != directory:
                _ENGINE, _ENGINE_PATH = None, None
                _ENGINE = NLI(directory); _ENGINE_PATH = directory
            for i in list(reversed(chosen))[:MAX_REMOVAL_TRIALS]:
                if len(chosen) <= 1 or i in protected:
                    continue
                hypotheses = _statements(sections[i])
                if hypotheses is None:
                    continue
                remaining = [j for j in chosen if j != i and _identity(sections[j]) == _identity(sections[i])]
                witnesses = set(); complete = bool(remaining)
                for hypothesis, raw in hypotheses:
                    if not complete:
                        break
                    guard = _guard_terms(raw)
                    options = [j for j in remaining if not (guard - _guard_terms(sections[j].text))]
                    # Lexical prioritization can miss redundancy but cannot itself remove a row.
                    words = set(re.findall(r"\w+", raw.casefold()))
                    options.sort(key=lambda j: (-len(words & set(re.findall(r"\w+", sections[j].text.casefold()))), sections[j].key))
                    found = None
                    for j in options[:4]:
                        scores = _ENGINE.classify(sections[j].text, hypothesis, budget, cache)
                        if scores and scores[1] >= MIN_ENTAILMENT and scores[0] <= MAX_CONTRADICTION:
                            found = j; break
                    if found is None:
                        complete = False
                    else:
                        witnesses.add(found)
                checked += 1
                if complete:
                    chosen.remove(i)
                    protected.update(witnesses)  # no circular or disappearing justifications
                    decisions.append({"section": i, "reason": "all_statements_nli_candidate",
                                      "support_sections": sorted(witnesses), "statements": len(hypotheses)})
        except Exhausted:
            limited = True
            chosen = exact_chosen
            decisions = [d for d in decisions if d["reason"] == "exact_source_span_covered"]
        finally:
            _LOCK.release()
    retained = set(chosen)
    receipt = {"checker": "source_statement_preservation_v1", "policy": policy,
        "status": "budget_limited_unchanged" if limited else "preservation_scan_finished",
        "question_sufficiency": "unassessed", "semantic_sufficiency_certified": False,
        "source_union_preserved": _exactly_covered(contexts(original), contexts(chosen)),
        "original_selected_groups": len(original), "selected_after_check": len(chosen),
        "added_groups": 0, "removed_groups": len(original) - len(chosen), "decisions": decisions,
        "nli_candidates_checked": checked, "model_pairs": budget.pairs, "cache_hits": budget.cache_hits,
        "model_pair_tokens": budget.pair_tokens, "runtime_seconds": round(budget.elapsed(), 3),
        "model_repo": MODEL_REPO if use_nli else None, "model_revision": MODEL_REVISION if use_nli else None,
        "probes_scored": 0, "probes_unscored": [], "answer_supported_changed": False,
        "corpus_absence_proven": False, "threshold_calibrated": False}
    return chosen + [i for i in ranking if i not in retained], len(chosen), receipt


def provision(directory):
    """Explicit host command only; no serving-time network access."""
    import tempfile
    import urllib.request
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("Use a fresh private model directory")
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{MODEL_REPO}/revision/{MODEL_REVISION}?blobs=true", timeout=60) as response:
        info = json.load(response)
    if info["sha"] != MODEL_REVISION:
        raise ValueError("Unexpected upstream revision")
    siblings = {x["rfilename"]: x for x in info["siblings"]}
    manifest = {"repo": MODEL_REPO, "revision": MODEL_REVISION, "license": "Apache-2.0", "files": {}}
    for name in FILES:
        entry = siblings[name]; lfs = entry.get("lfs") or {}
        size = entry.get("size") or lfs.get("size")
        if not isinstance(size, int) or not 0 < size < 400_000_000:
            raise ValueError("Missing or excessive pinned size")
        target = directory / name; target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent)
        try:
            h = hashlib.sha256(); count = 0
            with os.fdopen(fd, "wb") as out, urllib.request.urlopen(f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}", timeout=120) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("HTTPS required")
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > size:
                        raise ValueError("Model size exceeded")
                    h.update(block); out.write(block)
            if count != size or (lfs.get("sha256") and h.hexdigest() != lfs["sha256"]):
                raise ValueError("Upstream asset integrity failure")
            if name == MODEL_NAME and h.hexdigest() != MODEL_SHA256:
                raise ValueError("Unexpected NLI weights")
            os.chmod(tmp, 0o600); os.replace(tmp, target)
        finally:
            Path(tmp).unlink(missing_ok=True)
        manifest["files"][name] = {"bytes": count, "sha256": h.hexdigest()}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(directory / "manifest.json", 0o600)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Explicitly provision pinned local NLI assets")
    parser.add_argument("directory", type=Path)
    provision(parser.parse_args().directory)
