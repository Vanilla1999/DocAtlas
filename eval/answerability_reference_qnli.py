"""Installed-MCP experiment, not production activation or mocked-model acceptance.

Two preregistered readers: (1) current ONNX logits with official Transformers
postprocessing PER contiguous context; (2) published QNLI binary classifier.
The existing public MCP harness supplies real source-validated inputs. Only the
reader class is replaced at process startup. Retrieval/storage/source validation,
section compression, final delivery and the independent V40 oracle are unchanged.
No gold, keyword rules, query splitting, fitted thresholds, or corpus-absence claim.
"""
from __future__ import annotations

import gc
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

QNLI_REPO = "cross-encoder/qnli-electra-base"
QNLI_REVISION = "c7dea87"
QNLI_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json",
              "special_tokens_map.json", "vocab.txt", "onnx/model_quint8_avx2.onnx")
QA_REPO = "onnx-community/roberta-base-squad2-ONNX"
QA_REVISION = "6d1aeed784b6386659454d3be72de76fad8b73db"
UTILS_BLOB = "b30322b0071fff2f919bb0b2c48a77513430b6b4"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def provision(root):
    """Explicit online build step; exact revisions/hashes frozen before inference."""
    import urllib.request
    from huggingface_hub import HfApi, hf_hub_download
    root.mkdir(parents=True, exist_ok=True)
    models = {}
    for repo, rev, subdir, requested in (
        (QNLI_REPO, QNLI_REVISION, "qnli", QNLI_FILES),
        (QA_REPO, QA_REVISION, "qa-tokenizer", (
            "config.json", "tokenizer.json", "tokenizer_config.json",
            "special_tokens_map.json", "vocab.json", "merges.txt")),
    ):
        info = HfApi().model_info(repo, revision=rev, files_metadata=True)
        if not info.sha.startswith(rev):
            raise RuntimeError("resolved revision does not match frozen prefix")
        available = {s.rfilename for s in info.siblings}
        files = {}
        for name in requested:
            if name not in available:
                if name in {"config.json", "tokenizer.json", "onnx/model_quint8_avx2.onnx"}:
                    raise RuntimeError("required model asset missing: " + name)
                continue
            data = Path(hf_hub_download(repo, name, revision=info.sha)).read_bytes()
            target = root / subdir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[name] = {"bytes": len(data), "sha256": digest(data)}
        models[subdir] = {"repo": repo, "revision": info.sha, "files": files}
    url = "https://raw.githubusercontent.com/huggingface/transformers/v4.57.1/examples/pytorch/question-answering/utils_qa.py"
    data = urllib.request.urlopen(url, timeout=60).read()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if blob != UTILS_BLOB:
        raise RuntimeError("official reference changed; refusing an unreviewed reference")
    (root / "utils_qa.py").write_bytes(data)
    save(root / "FREEZE.json", {"models": models, "utils_qa": {
        "url": url, "git_blob": blob, "sha256": digest(data)},
        "policy": "fixed model class boundary; no V40 threshold selection; all admitted contiguous contexts; no question rewriting"})
    print("Provisioned immutable reference and QNLI assets", flush=True)


def verified_assets():
    root = Path(os.environ["PROBE_ASSETS"])
    manifest = json.loads((root / "FREEZE.json").read_text())
    for subdir, model in manifest["models"].items():
        for name, expected in model["files"].items():
            path = root / subdir / name
            if path.is_symlink() or path.stat().st_size != expected["bytes"] or digest(path.read_bytes()) != expected["sha256"]:
                raise RuntimeError("changed probe model bytes")
    if digest((root / "utils_qa.py").read_bytes()) != manifest["utils_qa"]["sha256"]:
        raise RuntimeError("changed reference code")
    return root, manifest


def record(question, value):
    key = digest(question.encode())
    save(Path(os.environ["PROBE_OUTPUT"]) / (key + ".json"), value)
    return key


def install_reader():
    import numpy as np
    from transformers import AutoTokenizer
    from docmancer.docs.application import answerability as product
    root, manifest = verified_assets()
    arm = os.environ["PROBE_ARM"]
    original_reader = product._Reader

    class Capture:
        """Observation of actual ONNX inference, not prerecorded logits or a mock."""
        def __init__(self, session):
            self.session, self.calls = session, []

        def run(self, outputs, feeds):
            values = self.session.run(outputs, feeds)
            self.calls.append(({k: v.copy() for k, v in feeds.items()}, [v.copy() for v in values]))
            return values

    class Examples(list):
        def __getitem__(self, item):
            if isinstance(item, str):
                return [row[item] for row in self]
            return super().__getitem__(item)

    class ReferenceReader(original_reader):
        def __init__(self, directory):
            super().__init__(directory)
            self.native = AutoTokenizer.from_pretrained(str(root / "qa-tokenizer"),
                local_files_only=True, trust_remote_code=False, use_fast=True)
            self.reference = load_module("frozen_hf_utils_qa", root / "utils_qa.py")

        def assess(self, question, contexts):
            session = self.session
            capture = Capture(session)
            self.session = capture
            try:
                current = super().assess(question, contexts)
            finally:
                self.session = session
            features, examples, decisions = [], Examples(), []
            call_index, mismatches = 0, []
            for i, context in enumerate(contexts):
                eid = "context-" + str(i)
                examples.append({"id": eid, "context": context["text"]})
                encoded = self.native(question, context["text"], truncation="only_second",
                    max_length=product.MAX_SEQUENCE, stride=product.OVERLAP, padding=False,
                    return_offsets_mapping=True, return_overflowing_tokens=True)
                for n, ids in enumerate(encoded["input_ids"]):
                    if call_index >= len(capture.calls):
                        raise RuntimeError("reference produced more features than actual inference")
                    feeds, _ = capture.calls[call_index]
                    if feeds["input_ids"][0].tolist() != ids or feeds["attention_mask"][0].tolist() != encoded["attention_mask"][n]:
                        mismatches.append({"context": i, "window": n, "call": call_index})
                    sequence = encoded.sequence_ids(n)
                    offsets = [list(pair) if sequence[j] == 1 else None
                               for j, pair in enumerate(encoded["offset_mapping"][n])]
                    features.append({"example_id": eid, "offset_mapping": offsets})
                    call_index += 1
            if call_index != len(capture.calls) or mismatches:
                record(question, {"arm": arm, "current": current, "tokenization_mismatches": mismatches,
                                  "reference_features": call_index, "actual_features": len(capture.calls)})
                raise RuntimeError("tokenization parity failed; do not compare mismatched logits")
            key = digest(question.encode())
            out = Path(os.environ["PROBE_OUTPUT"]) / key
            out.mkdir(parents=True, exist_ok=True)
            arrays = {f"{side}_{i}": np.asarray(values[j]).reshape(-1)
                      for i, (_, values) in enumerate(capture.calls)
                      for j, side in enumerate(("start", "end"))}
            np.savez_compressed(out / "actual_logits.npz", **arrays)
            with gzip.open(out / "features.json.gz", "wt", encoding="utf-8") as stream:
                json.dump({"examples": examples, "features": features,
                           "input_ids": [f["input_ids"][0].tolist() for f, _ in capture.calls]}, stream)
            predictions = self.reference.postprocess_qa_predictions(examples, features,
                ([v[0].reshape(-1) for _, v in capture.calls],
                 [v[1].reshape(-1) for _, v in capture.calls]),
                version_2_with_negative=True, n_best_size=20,
                max_answer_length=product.MAX_ANSWER_TOKENS, null_score_diff_threshold=0.0,
                output_dir=str(out), prefix="reference")
            fake = []
            for example in examples:
                answer = predictions[example["id"]]
                if answer and answer not in example["context"]:
                    fake.append(example["id"])
                decisions.append(bool(answer and answer in example["context"]))
            # Aggregate only decisions, never raw null scores across distinct sources.
            # HF's synthetic empty fallback is not evidence and blocks acceptance.
            decision = "unknown" if fake else ("candidate_answer" if any(decisions) else "no_answer")
            result = {**current, "decision": decision, "reference_context_candidates": sum(decisions),
                      "current_decision": current["decision"], "tokenization_equal": True,
                      "native_features": call_index, "synthetic_reference_candidates": fake,
                      "diagnostic_profile": "hf-reference-per-contiguous-context"}
            record(question, {"arm": arm, "current": current, "result": result})
            return result

    class QNLIReader:
        def __init__(self, directory):
            import onnxruntime as ort
            self.native = AutoTokenizer.from_pretrained(str(root / "qnli"),
                local_files_only=True, trust_remote_code=False, use_fast=True)
            options = ort.SessionOptions()
            options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            self.session = ort.InferenceSession(str(root / "qnli/onnx/model_quint8_avx2.onnx"),
                sess_options=options, providers=["CPUExecutionProvider"])
            self.names = {x.name for x in self.session.get_inputs()}
            self.meta = manifest["models"]["qnli"]

        def assess(self, question, contexts):
            if not question or len(self.native.encode(question, add_special_tokens=False)) > product.MAX_QUERY_TOKENS:
                raise product.AnswerabilityError("answerability_query_limit")
            started = time.monotonic()
            logits, calls, pair_tokens = [], 0, 0
            for i, context in enumerate(contexts):
                encoded = self.native(question, context["text"], truncation="only_second",
                    max_length=512, stride=product.OVERLAP, padding=False,
                    return_overflowing_tokens=True)
                for n, ids in enumerate(encoded["input_ids"]):
                    if calls >= product.MAX_PAIRS or time.monotonic() - started > product.MAX_SECONDS:
                        raise product.AnswerabilityError("answerability_resource_limit")
                    feeds = {k: np.asarray([encoded[k][n]], dtype=np.int64) for k in self.names}
                    value = self.session.run(None, feeds)[0]
                    if np.asarray(value).size != 1 or not math.isfinite(float(np.asarray(value).reshape(-1)[0])):
                        raise product.AnswerabilityError("answerability_invalid_logits")
                    logit = float(np.asarray(value).reshape(-1)[0])
                    # Native binary classifier argmax([0, logit]), NOT a fitted cutoff.
                    logits.append({"context": i, "window": n, "logit": logit,
                                   "label": "candidate" if logit > 0 else "unknown" if logit == 0 else "not_supported"})
                    calls += 1
                    pair_tokens += len(ids)
            if not calls:
                raise product.AnswerabilityError("answerability_empty_inputs")
            if time.monotonic() - started > product.MAX_SECONDS:
                raise product.AnswerabilityError("answerability_resource_limit")
            labels = {v["label"] for v in logits}
            decision = "candidate_answer" if "candidate" in labels else "unknown" if "unknown" in labels else "no_answer"
            result = {"decision": decision, "pairs": calls, "pair_tokens": pair_tokens,
                      "contexts": len(contexts), "seconds": time.monotonic() - started,
                      "scan_complete": True, "model_repo": QNLI_REPO,
                      "model_revision": self.meta["revision"], "diagnostic_profile": "qnli-native-binary",
                      "best_logit": max(v["logit"] for v in logits)}
            record(question, {"arm": arm, "result": result, "features": logits})
            return result

    if arm not in {"reference", "qnli"}:
        raise RuntimeError("unknown experimental arm")
    product._Reader = ReferenceReader if arm == "reference" else QNLIReader
    product._ENGINE, product._ENGINE_PATH = None, None
    gc.collect()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--provision":
        provision(Path(sys.argv[2]))
        return
    if "--worker" in sys.argv:
        install_reader()
    helper = load_module("answerability_original_integration", Path(__file__).with_name("answerability_integration.py"))
    # Spawn this exact entry point for each real MCP subprocess, not the old reader.
    helper.__file__ = str(Path(__file__).resolve())
    helper.main()


if __name__ == "__main__":
    main()
