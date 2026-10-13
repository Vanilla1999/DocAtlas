"""Paired installed public MCP comparison: native order versus pinned cross-encoder.

No oracle imports, lexical rules, top-k, score cutoff, text truncation or fallback.
Only a permutation of complete source-checked windows may reach the finalizer.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr
import importlib.metadata
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import database, deadline, files, integrity, ledger, pack, save, sha, snapshots
from run import load_dataset, source_directory, verify

REPO = Path(__file__).resolve().parents[2]


class LearnedOrder:
    def __init__(self, assets):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        self.tokenizer = Tokenizer.from_file(str(assets / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        config = json.loads((assets / "config.json").read_text())
        self.maximum = config["max_position_embeddings"]
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(assets / "onnx/model.onnx"), sess_options=options,
                                            providers=["CPUExecutionProvider"])
        self.session.disable_fallback()
        self.last = None
        self.total_batches = self.total_pairs = 0

    def __call__(self, *, question, passages):
        started = time.perf_counter()
        encodings = self.tokenizer.encode_batch([(question, passage) for passage in passages])
        lengths = [len(value.ids) for value in encodings]
        self.last = dict(question=question, input_text_sha256=[sha(p.encode()) for p in passages],
                         lengths=lengths, maximum=self.maximum, batches=0, pairs=0, scores=[],
                         status="started", truncated_pairs=0)
        if any(length > self.maximum for length in lengths):
            self.last["status"] = "unsupported_complete_input_length"
            raise ValueError("complete question/window exceeds model positions; no truncation or fallback")
        scores = []
        for offset in range(0, len(encodings), 8):
            batch = encodings[offset:offset + 8]
            width = max(len(value.ids) for value in batch)
            inputs = {
                "input_ids": self.np.asarray([value.ids + [0] * (width - len(value.ids)) for value in batch], dtype="int64"),
                "attention_mask": self.np.asarray([value.attention_mask + [0] * (width - len(value.ids)) for value in batch], dtype="int64"),
                "token_type_ids": self.np.asarray([value.type_ids + [0] * (width - len(value.ids)) for value in batch], dtype="int64"),
            }
            self.total_batches += 1
            self.last["batches"] += 1
            result = self.session.run(None, inputs)[0]
            if result.shape != (len(batch), 1) or not self.np.isfinite(result).all():
                raise ValueError("cross-encoder did not produce one finite logit per whole passage")
            scores.extend(float(value) for value in result[:, 0])
            self.total_pairs += len(batch)
            self.last["pairs"] += len(batch)
        order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
        self.last.update(status="returned", scores=scores, order=order, seconds=time.perf_counter() - started)
        return order


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "output", "work"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    verify(manifest)
    config = manifest["config"]
    if not config["runtime_authorized"] or args.output.exists() or args.work.exists():
        raise ValueError("authorized fresh output/work required")
    args.output.mkdir(parents=True)
    args.work.mkdir(parents=True, mode=0o700)
    for key in tuple(os.environ):
        if key.startswith("DOCATLAS_EXPERIMENT_"):
            del os.environ[key]
    os.environ.update(DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS="12000",
                      TIKTOKEN_CACHE_DIR=config["tokenizer_cache_dir"], TOKENIZERS_PARALLELISM="false",
                      HF_HUB_OFFLINE="1")
    import docmancer
    import tiktoken
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application.query_trace import query_trace
    from docmancer.docs.application.experimental_candidate_selection import (
        experimental_candidate_selector, experimental_selection_observer,
    )
    origin = Path(docmancer.__file__).resolve()
    if origin.is_relative_to(REPO) or not origin.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("installed runtime required")
    with zipfile.ZipFile(config["wheel"]) as archive:
        hashes = {name: sha(archive.read(name)) for name in archive.namelist()
                  if name.startswith("docmancer/") and not name.endswith("/")}
    for name, digest in hashes.items():
        if sha((origin.parent.parent / name).read_bytes()) != digest:
            raise ValueError("installed file differs from wheel: " + name)
    save(args.output / "INSTALLED_ORIGIN.json", dict(origin=str(origin), prefix=sys.prefix,
         installed_files_sha256=hashes, wheel_sha256=sha(Path(config["wheel"]).read_bytes()),
         versions={name: importlib.metadata.version(name) for name in
                   ("doc-atlas", "onnxruntime", "tokenizers", "numpy", "mcp", "tiktoken")}))
    tokenizer = tiktoken.get_encoding("o200k_base")
    spec = importlib.util.spec_from_file_location("fixture_runtime", REPO / "eval/evidence_quality_v2/runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    started = time.perf_counter()
    summary = dict(status="running", contexts=0, preparations=0, model_batches=0, model_pairs=0,
                   generator_calls=0, records=[], limit=12000)
    model = None
    try:
        with deadline(120):
            model = LearnedOrder(Path(config["assets"]))
        summary["model_load_seconds"] = time.perf_counter() - started
        dataset = Path(config["datasets"][0]["path"])
        cases, families = load_dataset(dataset)
        if config.get("case_ids"):
            cases = [case for case in cases if case["id"] in config["case_ids"]]
        case_number = 0
        for family in families:
            selected = [case for case in cases if case["project_group"] == family["id"]]
            if not selected:
                continue
            root = (args.work / ("0-" + family["id"]) / "project").resolve()
            documents = {name: (source_directory(dataset, family["id"]) / name).read_text() for name in family["paths"]}
            runtime.write_project(root, documents)
            with runtime.isolated_service(args.work / ("0-" + family["id"]) / "state") as (service, service_config):
                summary["preparations"] += 1
                ledger(args.output / "EXECUTION_LEDGER.jsonl", "prepare_docs", "started", family=family["id"])
                with deadline(180):
                    inventory = runtime.index_project(service, service_config, root)
                committed = snapshots(inventory, root, documents)
                initial_db, initial_files = database(inventory["storage_path"]), files(root)
                for arm in ("native", "learned"):
                    save(args.output / arm / "preparation" / ("0-" + family["id"] + ".json"),
                         dict(root=str(root), inventory=inventory, snapshot_sources=committed))
                ledger(args.output / "EXECUTION_LEDGER.jsonl", "prepare_docs", "returned", family=family["id"])
                for case in selected:
                    orders = ("native", "learned") if case_number % 2 == 0 else ("learned", "native")
                    pair = {}
                    for arm in orders:
                        verify(manifest)
                        remaining = int(config["wall_seconds"] - (time.perf_counter() - started))
                        if remaining <= 0 or summary["contexts"] >= config["context_calls"]:
                            raise TimeoutError("frozen wall/call cap")
                        destination = args.output / arm / "calls/0" / case["id"] / arm
                        arguments = dict(question=case["question"], project_path=str(root), scope="project")
                        receipts, trace = [], io.StringIO()
                        record = dict(case_id=case["id"], arm=arm, public_request=arguments, status="started")
                        save(destination / "metadata.json", record)
                        summary["contexts"] += 1
                        ledger(args.output / "EXECUTION_LEDGER.jsonl", "get_docs_context", "started", case_id=case["id"], arm=arm)
                        call_start = time.perf_counter()
                        model.last = None
                        try:
                            with deadline(min(120, remaining)), redirect_stderr(trace), query_trace(True), \
                                    experimental_candidate_selector(model if arm == "learned" else None), \
                                    experimental_selection_observer(receipts.append) as observation:
                                payload = call_docs_tool_payload("get_docs_context", arguments, service)
                            save(destination / "public-payload.json", payload)
                            save(destination / "selection.json", receipts)
                            save(destination / "model.json", model.last)
                            save(destination / "packed.json", pack(payload, tokenizer, 12000))
                            checks = integrity(payload, root, documents)
                            save(destination / "integrity.json", checks)
                            wire = json.dumps(payload, ensure_ascii=False)
                            cost = max(math.ceil(len(wire.encode()) / 4), len(tokenizer.encode(wire, disallowed_special=())))
                            record.update(status="returned", integrity_errors=checks["errors"], native_cost=cost,
                                          observer_errors=observation.errors, observer_calls=observation.calls)
                            pair[arm] = receipts
                            if checks["errors"] or observation.errors or observation.calls != 1 or cost > 12000:
                                raise ValueError("public source/observer/budget gate failed")
                        except Exception as exc:
                            record.update(status="error", error=str(exc))
                            save(destination / "model.json", model.last)
                            raise
                        finally:
                            record.update(seconds=time.perf_counter() - call_start,
                                database_unchanged=database(inventory["storage_path"]) == initial_db,
                                files_unchanged=files(root) == initial_files)
                            save(destination / "metadata.json", record)
                            (destination / "trace.jsonl").write_text(trace.getvalue())
                            summary["records"].append(record)
                            ledger(args.output / "EXECUTION_LEDGER.jsonl", "get_docs_context", record["status"], case_id=case["id"], arm=arm)
                        if not record["database_unchanged"] or not record["files_unchanged"]:
                            raise ValueError("read-only mutation")
                    equal = pair["native"][0]["pool"] == pair["learned"][0]["pool"]
                    save(args.output / "fairness" / (case["id"] + ".json"), dict(ordered_checked_pool_equal=equal))
                    if not equal:
                        raise ValueError("unequal paired checked pool")
                    case_number += 1
        verify(manifest)
        summary["status"] = "completed" if summary["contexts"] == config["context_calls"] else "incomplete"
    except Exception as exc:
        summary.update(status="error", error_type=type(exc).__name__, error=str(exc))
    finally:
        summary.update(seconds=time.perf_counter() - started,
                       model_batches=model.total_batches if model else 0, model_pairs=model.total_pairs if model else 0)
        save(args.output / "SUMMARY.json", summary)
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
