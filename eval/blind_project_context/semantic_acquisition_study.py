"""Frozen, offline multilingual-E5 candidate recall study (not a product path).

Read the real prepared SQLite retrieval_children, embed every active child, and
rank by exact cosine for the unchanged question and its supplied translation.
The existing 256-child, 131072-token and 1-MiB acquisition ceilings are retained.
20/50/128 are descriptive cuts of that same ranking, never tuned thresholds.

The plan and ranking are written and hashed before loading the oracle or the
baseline's per-fact results. Only aggregate dev/holdout slices are printed.
This measures candidate availability, not admission, delivered context, or an
agent's final answer. Combining lexical and semantic pools uses extra capacity.

Example (models must already be provisioned from the pinned official revision):
    ORT_DISABLE_TELEMETRY=1 python semantic_acquisition_study.py plan \
        --source-tree REPO --prepared-root WORK --baseline SCORE --model-dir MODEL --out OUT
    # Same arguments for benchmark, embed, rank, score; or all after plan.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import sys
import time

# Set before any optional ONNX/FastEmbed import; sessions also opt out below.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MODEL_FILES = {
    "model.onnx": (470268510, "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665"),
    "tokenizer.json": (17082730, "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39"),
}
KS = (20, 50, 128, 256)
MAX_LENGTH = 512


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def source_state(path: Path) -> dict:
    return {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip(),
            "dirty": subprocess.check_output(["git", "status", "--porcelain"], cwd=path, text=True).splitlines()}


def verify_assets(directory: Path) -> dict:
    result = {}
    for name, (size, expected) in MODEL_FILES.items():
        path = directory / name
        if path.is_symlink() or path.stat().st_size != size or digest(path) != expected:
            raise ValueError(f"model asset does not match the pinned revision: {name}")
        result[name] = {"bytes": size, "sha256": expected}
    return result


def plan(args) -> None:
    from corpus import build, documents
    from docmancer.retrieval.experimental_acquisition import (
        ACQUISITION_CANDIDATES, ACQUISITION_ESTIMATED_TOKENS, ACQUISITION_TEXT_BYTES,
    )
    if (args.out / "plan.json").exists():
        raise ValueError("plan already exists; use a later phase or a new output directory")
    args.out.mkdir(parents=True, exist_ok=True)
    assets = verify_assets(args.model_dir)
    projects = build(args.out / "verified-corpora")
    texts, text_ids, corpora, stats, document_hashes = [], {}, {}, {}, {}

    def input_id(text: str) -> int:
        if text not in text_ids:
            text_ids[text] = len(texts)
            texts.append(text)
        return text_ids[text]

    for name, project in projects.items():
        docs = documents(project)
        document_hashes[name] = {path: digest(project / path) for path in sorted(docs)}
        document_hashes[name]["docatlas.project-docs.yaml"] = digest(project / "docatlas.project-docs.yaml")
        db = args.prepared_root / f"{name}-0/docatlas-home/mcp-members/members.db"
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT source_path, char_start, char_end, display_text, retrieval_text,
                       display_token_estimate, parent_logical_id, doc_scope,
                       stable_chunk_id, authority, lifecycle_status, source_class
                FROM retrieval_children
                WHERE generation_id=(SELECT active_generation_id FROM index_state WHERE singleton=1)
                ORDER BY source_path, char_start, char_end, retrieval_content_hash, stable_chunk_id
            """).fetchall()
        checked = []
        for row in rows:
            path, start, end = row["source_path"], row["char_start"], row["char_end"]
            if path not in docs or docs[path][start:end] != row["display_text"]:
                raise ValueError("prepared child is not an exact span of the sealed corpus")
            if row["authority"] != "source_of_truth" or row["source_class"] != "project_file":
                raise ValueError("unexpected source policy in prepared corpus")
            if row["lifecycle_status"] != "active":
                raise ValueError("study expects the frozen active-document corpus")
            checked.append({"path": path, "start": start, "end": end,
                            "body": row["display_text"], "key": row["stable_chunk_id"],
                            "estimated_tokens": row["display_token_estimate"],
                            "input_id": input_id("passage: " + row["retrieval_text"])})
        if set(docs) != {row["path"] for row in checked}:
            raise ValueError("prepared index does not contain the complete sealed corpus")
        corpora[name] = checked
        stats[name] = {"documents": len(docs), "children": len(checked),
                       "parents": len({row["parent_logical_id"] for row in rows}),
                       "scopes": dict(Counter(row["doc_scope"] for row in rows)),
                       "lifecycle_statuses": dict(Counter(row["lifecycle_status"] for row in rows)),
                       "database_sha256": digest(db)}
    passage_count = len(texts)
    cases = []
    for case in read(args.source_tree / "eval/blind_project_context/questions.json")["cases"]:
        lanes = list(dict.fromkeys(q for q in (case["question"], case.get("search_question")) if q))
        cases.append({key: case[key] for key in ("id", "topic_id", "split", "lang")}
                     | {"input_ids": [input_id("query: " + query) for query in lanes]})
    save(args.out / "inputs.json", texts)
    save(args.out / "corpora.json", corpora)
    save(args.out / "cases.json", cases)
    manifest = {
        "schema_version": 1, "created_at_utc": now(), "source_tree": source_state(args.source_tree),
        "study_tree": source_state(Path(__file__).resolve().parents[2]),
        "script_sha256": digest(Path(__file__)), "model": MODEL_ID, "revision": MODEL_REVISION,
        "assets": assets, "input_hashes": {name: digest(args.out / name)
                                            for name in ("inputs.json", "corpora.json", "cases.json")},
        "sealed_hashes": {name: digest(args.source_tree / "eval/blind_project_context" / name)
                          for name in ("questions.json", "oracle.json", "witness-audit.json", "corpus-lock.json")},
        "helper_hashes": {name: digest(args.source_tree / name) for name in (
            "eval/blind_project_context/corpus.py", "eval/blind_project_context/score.py",
            "docmancer/retrieval/experimental_acquisition.py")},
        "baseline_sha256": digest(args.baseline), "corpora": stats,
        "verified_document_hashes": document_hashes, "unique_passages": passage_count,
        "unique_queries": len(texts) - passage_count,
        "recipe": {"passage_field": "retrieval_children.retrieval_text", "prefixes": ["passage: ", "query: "],
                   "pooling": "attention-masked mean; L2 normalization", "dtype": "float32",
                   "max_length": MAX_LENGTH, "truncation": "tokenizer right truncation, retaining special tokens",
                   "search": "exact cosine over all active children, without lexical pruning",
                   "tie_break": "source_path, char_start, char_end, retrieval_content_hash, stable_chunk_id",
                   "lanes": "unchanged original question and supplied full translation; top-K per lane then union",
                   "primary_k": ACQUISITION_CANDIDATES, "descriptive_k": list(KS),
                   "descriptive_cut_order": "first K admitted children from the raw top-256; equivalent to raw top-K when resource_skipped=0",
                   "estimated_token_ceiling": ACQUISITION_ESTIMATED_TOKENS,
                   "display_byte_ceiling": ACQUISITION_TEXT_BYTES,
                   "scope": "complete prepared project corpus, including catalogued module documents",
                   "oracle_used_in_embedding_or_ranking": False},
        "runtime": {"threads": args.threads, "batch_size": args.batch_size, "telemetry": "disabled"},
        "limitations": ["Candidate recall only, not admission or end-to-end delivery.",
                        "256 candidates applies per lane, so a translated question can union up to 512 children.",
                        "Lexical+semantic union uses additional candidates; it is not a fixed-total-budget hybrid.",
                        "Embedding input after 512 tokens is not read by the model.",
                        "Timing can be affected by concurrent work and is not a controlled model comparison."]}
    if manifest["recipe"]["primary_k"] != max(KS):
        raise ValueError("study K no longer matches the production acquisition ceiling")
    save(args.out / "plan.json", manifest)
    print(json.dumps({"phase": "plan_frozen", "corpora": stats, "unique_passages": passage_count,
                      "unique_queries": len(texts) - passage_count, "plan_sha256": digest(args.out / "plan.json")}), flush=True)


def check_plan(args) -> dict:
    manifest = read(args.out / "plan.json")
    if manifest["script_sha256"] != digest(Path(__file__)):
        raise ValueError("study script changed after the plan was frozen")
    if source_state(args.source_tree) != manifest["source_tree"]:
        raise ValueError("source tree changed after plan freeze")
    for name, expected in manifest["helper_hashes"].items():
        if digest(args.source_tree / name) != expected:
            raise ValueError("study helper changed after plan freeze")
    for name, expected in manifest["input_hashes"].items():
        if digest(args.out / name) != expected:
            raise ValueError(f"frozen input changed: {name}")
    for corpus, paths in manifest["verified_document_hashes"].items():
        for path, expected in paths.items():
            if digest(args.out / "verified-corpora" / corpus / "project" / path) != expected:
                raise ValueError("verified corpus document changed after plan freeze")
    return manifest


class Encoder:
    def __init__(self, directory: Path, threads: int):
        import onnxruntime as ort
        ort.disable_telemetry_events()
        from tokenizers import Tokenizer
        verify_assets(directory)
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_padding()
        self.tokenizer.no_truncation()
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(directory / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.inputs = {item.name for item in self.session.get_inputs()}
        if "last_hidden_state" not in {item.name for item in self.session.get_outputs()}:
            raise ValueError("pinned model does not expose token states for the E5 pooling recipe")
        self.pad_id = self.tokenizer.token_to_id("<pad>")
        if self.pad_id is None:
            raise ValueError("pinned tokenizer is missing its padding token")

    def tokenize(self, texts: list[str]):
        self.tokenizer.no_truncation()
        full_lengths = [len(item.ids) for item in self.tokenizer.encode_batch(texts)]
        self.tokenizer.enable_truncation(max_length=MAX_LENGTH, direction="right")
        encoded = self.tokenizer.encode_batch(texts)
        return encoded, full_lengths

    def embed(self, encodings):
        import numpy as np
        width = max(len(item.ids) for item in encodings)
        ids = np.full((len(encodings), width), self.pad_id, dtype=np.int64)
        mask = np.zeros_like(ids)
        types = np.zeros_like(ids)
        for index, encoding in enumerate(encodings):
            size = len(encoding.ids)
            ids[index, :size] = encoding.ids
            mask[index, :size] = encoding.attention_mask
            types[index, :size] = encoding.type_ids
        feeds = {key: value for key, value in {"input_ids": ids, "attention_mask": mask,
                                              "token_type_ids": types}.items() if key in self.inputs}
        hidden = self.session.run(["last_hidden_state"], feeds)[0]
        if hidden.shape != (len(encodings), width, 384):
            raise ValueError("unexpected pinned E5 output shape")
        masked = mask[..., None].astype(np.float32)
        pooled = (hidden * masked).sum(axis=1) / masked.sum(axis=1)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        if not np.isfinite(pooled).all() or (norms <= 0).any():
            raise ValueError("invalid model embedding")
        return (pooled / norms).astype(np.float32)


def encode(args, *, benchmark: bool = False) -> None:
    import numpy as np
    manifest = check_plan(args)
    plan_hash = digest(args.out / "plan.json")
    completed_receipt = args.out / "embedding-receipt.json"
    if not benchmark and completed_receipt.exists():
        previous = read(completed_receipt)
        if (previous["plan_sha256"] == plan_hash
                and digest(args.out / "embeddings.npy") == previous["embeddings_sha256"]):
            print(json.dumps({"phase": "embed_already_complete", "inputs_encoded": previous["inputs_encoded"]}), flush=True)
            return
        raise ValueError("completed embeddings do not match the frozen plan")
    texts = read(args.out / "inputs.json")
    started = time.perf_counter()
    engine = Encoder(args.model_dir, manifest["runtime"]["threads"])
    encoded, lengths = engine.tokenize(texts)
    startup = time.perf_counter() - started
    if benchmark:
        # Hash sampling is independent of queries, oracle, and retrieval quality.
        sample = sorted(range(manifest["unique_passages"]),
                        key=lambda i: hashlib.sha256(texts[i].encode()).digest())[:128]
        sample.sort(key=lambda i: (len(encoded[i].ids), i))
        work = sample
    else:
        work = sorted(range(len(texts)), key=lambda i: (len(encoded[i].ids), i))
    done, previous_seconds = set(), 0.0
    partial = args.out / "embeddings.partial.npy"
    progress = args.out / "embedding-progress.json"
    if benchmark:
        values = np.zeros((len(texts), 384), dtype=np.float32)
    elif progress.exists():
        saved = read(progress)
        if saved["plan_sha256"] != plan_hash:
            raise ValueError("embedding checkpoint belongs to a different plan")
        resume_path = partial if partial.exists() else args.out / "embeddings.npy"
        values = np.load(resume_path, mmap_mode="r+", allow_pickle=False)
        if values.shape != (len(texts), 384) or values.dtype != np.float32:
            raise ValueError("embedding checkpoint shape or dtype changed")
        done = set(saved["completed_indices"])
        if resume_path != partial and done != set(range(len(texts))):
            raise ValueError("final embedding file exists without a complete checkpoint")
        if hashlib.sha256(values[sorted(done)].tobytes()).hexdigest() != saved["completed_vectors_sha256"]:
            raise ValueError("completed checkpoint vectors changed")
        previous_seconds = saved["inference_seconds"]
        work = [index for index in work if index not in done]
    else:
        values = np.lib.format.open_memmap(partial, mode="w+", dtype=np.float32, shape=(len(texts), 384))
    batch_size = manifest["runtime"]["batch_size"]
    inference_started = time.perf_counter()
    last_notice = inference_started

    def checkpoint() -> None:
        if benchmark:
            return
        values.flush()
        pending = progress.with_suffix(".tmp")
        save(pending, {"plan_sha256": plan_hash, "completed_indices": sorted(done),
                       "completed_vectors_sha256": hashlib.sha256(values[sorted(done)].tobytes()).hexdigest(),
                       "inference_seconds": previous_seconds + time.perf_counter() - inference_started})
        os.replace(pending, progress)

    for start in range(0, len(work), batch_size):
        indices = work[start:start + batch_size]
        values[indices] = engine.embed([encoded[i] for i in indices])
        done.update(indices)
        if time.perf_counter() - last_notice >= 30:
            checkpoint()
            print(json.dumps({"phase": "embedding", "completed": len(done),
                              "total": len(texts), "seconds": round(previous_seconds + time.perf_counter() - inference_started, 1)}), flush=True)
            last_notice = time.perf_counter()
    elapsed = previous_seconds + time.perf_counter() - inference_started
    measured = work if benchmark else list(range(len(texts)))
    receipt = {"phase": "benchmark" if benchmark else "embed", "finished_at_utc": now(),
               "startup_seconds": round(startup, 3), "inference_seconds": round(elapsed, 3),
               "inputs_encoded": len(measured), "batch_size": batch_size,
               "input_tokens_before_truncation": sum(lengths[i] for i in measured),
               "truncated_inputs": sum(lengths[i] > MAX_LENGTH for i in measured),
               "truncated_tokens": sum(max(0, lengths[i] - MAX_LENGTH) for i in measured),
               "max_input_tokens": max(lengths[i] for i in measured),
               "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
               "plan_sha256": digest(args.out / "plan.json")}
    if benchmark:
        receipt["rough_full_inference_seconds"] = round(elapsed * len(texts) / len(work), 1)
    else:
        if done != set(range(len(texts))):
            raise ValueError("embedding phase did not complete every frozen input")
        checkpoint()
        del values
        if partial.exists():
            os.replace(partial, args.out / "embeddings.npy")
        receipt["embeddings_sha256"] = digest(args.out / "embeddings.npy")
        receipt["all_input_lengths"] = lengths
    save(args.out / ("benchmark.json" if benchmark else "embedding-receipt.json"), receipt)
    print(json.dumps({key: value for key, value in receipt.items() if key != "all_input_lengths"}), flush=True)


def rank(args) -> None:
    import numpy as np
    manifest = check_plan(args)
    receipt = read(args.out / "embedding-receipt.json")
    if receipt["plan_sha256"] != digest(args.out / "plan.json"):
        raise ValueError("embedding receipt belongs to another plan")
    if digest(args.out / "embeddings.npy") != receipt["embeddings_sha256"]:
        raise ValueError("embeddings changed after inference")
    values = np.load(args.out / "embeddings.npy", allow_pickle=False)
    corpora, cases = read(args.out / "corpora.json"), read(args.out / "cases.json")
    primary = manifest["recipe"]["primary_k"]
    results = []
    for corpus, rows in corpora.items():
        matrix = values[[row["input_id"] for row in rows]]
        for case in cases:
            lanes = []
            for input_id in case["input_ids"]:
                similarities = matrix @ values[input_id]
                order = np.argsort(-similarities, kind="stable")[:primary]
                selected, tokens, size, skipped = [], 0, 0, 0
                for raw_index in order:
                    index = int(raw_index)
                    row = rows[index]
                    t, b = max(0, row["estimated_tokens"]), len(row["body"].encode("utf-8"))
                    if (tokens + t > manifest["recipe"]["estimated_token_ceiling"]
                            or size + b > manifest["recipe"]["display_byte_ceiling"]):
                        skipped += 1
                        continue
                    selected.append(index)
                    tokens += t
                    size += b
                lanes.append({"input_id": input_id, "rows": selected, "resource_skipped": skipped})
            results.append({"corpus": corpus, **case, "lanes": lanes})
    save(args.out / "rankings.json", results)
    save(args.out / "ranking-receipt.json", {"finished_at_utc": now(),
         "plan_sha256": digest(args.out / "plan.json"), "rankings_sha256": digest(args.out / "rankings.json"),
         "embedding_receipt_sha256": digest(args.out / "embedding-receipt.json"),
         "embeddings_sha256": receipt["embeddings_sha256"],
         "oracle_loaded": False, "ranked_cases": len(results),
         "resource_skipped": sum(lane["resource_skipped"] for item in results for lane in item["lanes"])})
    print(json.dumps(read(args.out / "ranking-receipt.json")), flush=True)


def score(args) -> None:
    from corpus import documents
    from score import placements
    manifest = check_plan(args)
    rank_receipt = read(args.out / "ranking-receipt.json")
    if rank_receipt["plan_sha256"] != digest(args.out / "plan.json"):
        raise ValueError("ranking receipt belongs to another plan")
    if (rank_receipt["embedding_receipt_sha256"] != digest(args.out / "embedding-receipt.json")
            or rank_receipt["embeddings_sha256"] != digest(args.out / "embeddings.npy")):
        raise ValueError("embedding provenance changed after ranking")
    if digest(args.out / "rankings.json") != rank_receipt["rankings_sha256"]:
        raise ValueError("ranking changed before scoring")
    base_dir = args.source_tree / "eval/blind_project_context"
    for name, expected in manifest["sealed_hashes"].items():
        if digest(base_dir / name) != expected:
            raise ValueError(f"sealed dataset changed: {name}")
    if digest(args.baseline) != manifest["baseline_sha256"]:
        raise ValueError("baseline changed after plan freeze")
    # First interpretation of oracle/fact metadata occurs after ranking is sealed.
    oracle = {item["topic_id"]: item for item in read(base_dir / "oracle.json")["topics"]}
    audit = {item["fact_id"]: item for item in read(base_dir / "witness-audit.json")["facts"]}
    baseline = read(args.baseline)
    if baseline["anomalies"]:
        raise ValueError("baseline contains anomalies")
    for key, filename in (("questions_sha256", "questions.json"), ("oracle_sha256", "oracle.json")):
        if baseline[key] != manifest["sealed_hashes"][filename]:
            raise ValueError("baseline belongs to another sealed dataset")
    old = {(case["corpus"], case["case_id"]): case for case in baseline["cases"]}
    rankings = read(args.out / "rankings.json")
    if set(old) != {(case["corpus"], case["id"]) for case in rankings}:
        raise ValueError("baseline and ranking case sets differ")
    corpora = read(args.out / "corpora.json")
    matches, equivalence_checks = {}, 0
    for corpus, rows in corpora.items():
        docs = documents(args.out / "verified-corpora" / corpus / "project")
        for topic in oracle.values():
            for fact in topic["facts"]:
                spans = []
                for place in audit[fact["fact_id"]]["occurrences"][corpus]:
                    found = placements(docs[place["path"]], place["line_start"], place["line_end"], fact["quote"])
                    if not found:
                        raise ValueError("an audited occurrence is absent from the verified corpus")
                    spans.extend((place["path"], start, end) for start, end in found)
                matches[corpus, fact["fact_id"]] = {
                    index for index, row in enumerate(rows)
                    if any(row["path"] == path and row["start"] <= start and end <= row["end"]
                           for path, start, end in spans)}
                # The historical observer checked literal quote presence. Verify
                # that the stricter audited-span criterion is exactly equivalent
                # on this corpus, rather than mixing two acquisition metrics.
                raw_matches = {index for index, row in enumerate(rows) if fact["quote"] in row["body"]}
                if matches[corpus, fact["fact_id"]] != raw_matches:
                    raise ValueError("audited containment and historical quote-presence metrics differ")
                equivalence_checks += 1
    summaries = defaultdict(Counter)
    for case in rankings:
        previous = old[case["corpus"], case["id"]]
        if any(previous[key] != case[key] for key in ("topic_id", "split", "lang")):
            raise ValueError("baseline case metadata changed")
        if any(type(f["in_candidates"]) is not bool for f in previous["facts"]):
            raise ValueError("baseline lacks complete passive acquisition observations")
        lexical = {f["fact_id"] for f in previous["facts"] if f["in_candidates"] is True}
        historic_missing = {f["fact_id"] for f in previous["facts"]
                            if not f["found"] and f["in_candidates"] is False}
        facts = {f["fact_id"] for f in oracle[case["topic_id"]]["facts"]}
        if {f["fact_id"] for f in previous["facts"]} != facts:
            raise ValueError("baseline and oracle fact sets differ")
        universe = {f for f in facts if matches[case["corpus"], f]}
        for k in KS:
            selected = set().union(*(set(lane["rows"][:k]) for lane in case["lanes"]))
            semantic = {f for f in facts if matches[case["corpus"], f] & selected}
            key = f"{case['split']}/{case['corpus']}/{case['lang']}/k={k}"
            summaries[key].update(cases=1, facts_total=len(facts), universe_facts=len(universe),
                                  lexical_candidate_facts=len(lexical), semantic_candidate_facts=len(semantic),
                                  union_candidate_facts=len(lexical | semantic),
                                  lexical_missing=len(facts - lexical),
                                  historical_unresolved_missing=len(historic_missing),
                                  semantic_recovers_historical_missing=len(semantic & historic_missing),
                                  delivered_without_observed_candidate=len((facts - lexical) - historic_missing),
                                  semantic_recovers_lexical_missing=len(semantic - lexical),
                                  lexical_only=len(lexical - semantic),
                                  semantic_all_facts=int(semantic == facts),
                                  union_all_facts=int((lexical | semantic) == facts),
                                  semantic_unique_children=len(selected))
    totals = {}
    for k in KS:
        aggregate = Counter()
        for key, value in summaries.items():
            if key.endswith(f"/k={k}"):
                aggregate.update(value)
        totals[str(k)] = dict(aggregate)
    result = {"schema_version": 1, "finished_at_utc": now(), "plan_sha256": digest(args.out / "plan.json"),
              "rankings_sha256": rank_receipt["rankings_sha256"], "primary_k": max(KS),
              "metric": "audited exact quote wholly available in one retrieved original child",
              "historical_quote_metric_equivalence_checks": equivalence_checks,
              "slices": {key: dict(value) for key, value in sorted(summaries.items())}, "totals": totals,
              "limitations": manifest["limitations"]}
    save(args.out / "summary.json", result)
    print(json.dumps({"phase": "scored", "primary_k": max(KS), "totals": totals}), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=("plan", "benchmark", "embed", "rank", "score", "all"))
    for name in ("source-tree", "prepared-root", "baseline", "model-dir", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    for name in ("source_tree", "prepared_root", "baseline", "model_dir", "out"):
        setattr(args, name, getattr(args, name).resolve())
    if args.threads < 1 or args.batch_size < 1:
        parser.error("threads and batch size must be positive")
    sys.path.insert(0, str(args.source_tree))
    sys.path.insert(0, str(args.source_tree / "eval/blind_project_context"))
    if args.phase in ("plan", "all") and not (args.phase == "all" and (args.out / "plan.json").exists()):
        plan(args)
    if args.phase == "benchmark":
        encode(args, benchmark=True)
    if args.phase in ("embed", "all"):
        encode(args)
    if args.phase in ("rank", "all"):
        rank(args)
    if args.phase in ("score", "all"):
        score(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
