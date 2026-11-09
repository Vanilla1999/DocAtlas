"""Publish source-exact Q6 review evidence without local capabilities or paths.

Export requires the installed evaluation environment, solely to decode saved
MCP representations. --verify needs only Python's standard library and the
unchanged repository sources. Neither operation starts MCP or runs a model.
The output is a new directory published atomically; existing output is refused.
Gzip files have no timestamp or filename and are deterministic.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STABLE_FIELDS = ("path_or_url", "section", "snippet", "line_start", "line_end",
                 "scope", "version_binding", "authority", "instruction_trust", "content_sha256")
RAW_NAMES = ("run-config.json", "source-manifest.json", "calls.json", "prepare.json",
             "tools.json", "response.json", "wire.txt", "observation.jsonl", "server.stderr",
             "state-before.json", "state-after.json", "timing.json", "summary.json")
SUMMARY_FIELDS = ("boundary", "question", "case", "mode", "profile", "observed", "scope",
                  "documents", "catalog_sha256", "oracle_sha256", "recorded_harness_sha256",
                  "evaluator_sha256", "calls", "seconds", "budget", "source_rows", "facts",
                  "delivered_facts", "source_fidelity", "source_and_index_unchanged", "observation",
                  "exact_wire_parity", "wire_sha256", "delivered_rows_sha256", "status", "reason_code",
                  "answer_quality", "provider_usage")
DECISION_FIELDS = ("evidence_id", "line_start", "line_end", "decision", "first_decision",
                   "first_unit_rows", "first_selected_before", "first_gain_per_cost", "first_relevance",
                   "first_cost_bytes", "first_redundancy", "gain_per_cost", "relevance", "cost_bytes",
                   "redundancy", "unit_rows", "selected_before", "trial_text_bytes", "fit_check",
                   "joint_output", "semantic_lane_scores")
LEXICAL_FIELDS = ("mode", "query_terms", "matched_terms", "exact_terms", "missing_exact_terms",
                  "query_term_count", "matched_term_count", "match_ratio", "content_lexical_cost",
                  "lexical_score", "field_matches", "routing_only", "routing_match_ratio")
SEMANTIC_FIELDS = frozenset((
    "event recipe mode status ranking_only model_pairs model_forwards model_input_tokens rows lanes "
    "context_is_delivered_evidence diagnostics_status error_type observer_error failed_scorer_receipt "
    "evidence_id path source_identity_sha256 source_sha256 heading_path body available_context_spans "
    "context_spans context_sha256 context_utf8_bytes source_recheck scores identity score raw_logit pairs "
    "body_tokens ancestor_tokens body_token_coverage body_character_extent intervals_recorded intervals_omitted "
    "pair_token_intervals role char_start char_end line_start line_end utf8_bytes sha256 native_derivation_sha256 "
    "query receipt units inference_seconds model_load_attempts model_loads coverage aggregation "
    "maximum_sequence_length pair_special_tokens query_tokens total_seconds asset_verification_seconds "
    "model_import_seconds model_load_seconds failed_pass model model_id revision assets_sha256 device dtype "
    "torch transformers threads interop_threads max_length truncation tie_break lane whole_pair ancestor "
    "own_body_gate contextual_score own_body_score lock_wait_seconds"
).split())
PRIVATE_KEYS = frozenset({"source_uri", "continuation_token", "environment", "raw_document",
                          "_reference_evidence", "member_binding", "_native_discovery_receipt"})
LOCAL_PATH = re.compile(r"(?:^|[\s\"'(])/(?:workspace|home|root|tmp|opt|mnt)/")
HASH = re.compile(r"[0-9a-f]{64}\Z")


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    if path.suffix == ".gz":
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as handle:
            handle.write(data)
        data = buffer.getvalue()
    path.write_bytes(data)


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Expected a literal relative public path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError("Non-public path refused")
    return value


def inspect_public(value, key=None):
    """Reject leaks; never rewrite source-authored text to make a check pass."""
    if isinstance(value, dict):
        if PRIVATE_KEYS.intersection(value):
            raise ValueError("Private capability or environment field in export")
        for name, item in value.items():
            inspect_public(item, name)
    elif isinstance(value, list):
        for item in value:
            inspect_public(item, key)
    elif isinstance(value, str) and key != "snippet":
        if "docatlas://" in value or LOCAL_PATH.search(value):
            raise ValueError("Local runtime path or live URI in public metadata")


def stable(rows):
    return [{key: row.get(key) for key in STABLE_FIELDS} for row in rows]


def source_rows(rows, documents):
    result = []
    for row in rows:
        path = relative(row["path_or_url"])
        if path not in documents:
            raise ValueError("Source outside frozen manifest")
        lines = documents[path].splitlines(keepends=True)
        start, end, snippet = row["line_start"], row["line_end"], row["snippet"]
        if not (type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)):
            raise ValueError("Invalid source coordinates")
        if not snippet or "".join(lines[start - 1:end]).count(snippet) != 1:
            raise ValueError("Source bytes do not match the declared range uniquely")
        if "snippet_sha256" in row and row["snippet_sha256"] != sha(snippet.encode()):
            raise ValueError("Stored snippet checksum differs from source bytes")
        public = {key: row.get(key) for key in ("evidence_id", *STABLE_FIELDS)}
        public["snippet_sha256"] = sha(snippet.encode())
        result.append(public)
    inspect_public(result)
    return result


def semantic(value, parent=None):
    """Preserve the complete known scorer receipt; omit raw exception prose."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "error":
                out["error_details_sha256"] = sha(str(item).encode())
                continue
            if key in SEMANTIC_FIELDS or parent in {"lanes", "scores", "assets_sha256"}:
                out[key] = semantic(item, key)
        return out
    if isinstance(value, list):
        return [semantic(item, parent) for item in value]
    inspect_public(value, parent)
    return value


def observation_exports(events, documents):
    acquisitions, selections, semantics = [], [], []
    for event in events:
        if event.get("event") == "acquisition":
            pool = []
            for row in event["rows"]:
                metadata = row.get("metadata") or {}
                path = relative(metadata.get("project_doc_path") or metadata.get("source_path"))
                if path not in documents:
                    raise ValueError("Acquired path outside corpus")
                match = {key: metadata["lexical_match"][key] for key in LEXICAL_FIELDS
                         if key in metadata.get("lexical_match", {})}
                if len(encode(match)) > 16384:
                    raise ValueError("Unexpectedly unbounded lexical metadata")
                pool.append({"rank": row["rank"], "path": path, "text_sha256": sha(row["text"].encode()),
                             "score": row["score"], "lexical_match": match})
            acquisitions.append({"query": event["query"], "rows": pool})
        elif event.get("event") == "joint_selection" and event.get("before"):
            pool = source_rows(event["before"]["sources"] or [], documents)
            by_id = {row["evidence_id"]: row for row in pool}
            trace = ((event.get("diagnostics") or {}).get("docs_context_projection") or {}).get(
                "joint_selection_observation") or {}
            decisions = []
            for row in trace.get("rows", []):
                reference = by_id[row["evidence_id"]]
                decisions.append({**{key: row[key] for key in DECISION_FIELDS if key in row},
                                  "path": reference["path_or_url"], "section": reference["section"],
                                  "snippet_sha256": reference["snippet_sha256"]})
            selections.append({"checked_sources": pool, "decisions": decisions,
                               "trace_row_count": trace.get("row_count"),
                               "trace_row_limit": trace.get("row_limit"),
                               "trace_omitted_rows": trace.get("omitted_rows"),
                               "pool_pruning": {key: value for key, value in (trace.get("pool_pruning") or {}).items()
                                                if isinstance(value, (str, int, float, bool)) or value is None},
                               "source_selection": {key: value for key, value in (event.get("after", {}).get("source_selection") or {}).items()
                                                    if isinstance(value, (str, int, float, bool)) or value is None},
                               "query_plan_sha256": sha(encode(event["before"]["query_plan"]))})
            if trace.get("semantic_relevance") and not any(e.get("event") == "semantic_relevance" for e in events):
                semantics.append(semantic(trace["semantic_relevance"]))
        elif event.get("event") == "semantic_relevance":
            semantics.append(semantic(event))
    for value in (acquisitions, selections, semantics):
        inspect_public(value)
    return acquisitions, selections, semantics


def state_proof(run):
    before, after = run / "state-before.json", run / "state-after.json"
    if not before.exists() or not after.exists():
        return {"status": "not_recorded", "logical_equal": None}
    left, right = read(before), read(after)
    return {"status": "recorded", "logical_equal": left == right,
            "before_sha256": sha(encode(left)), "after_sha256": sha(encode(right)),
            "tables": {key: {"before_rows": len(left.get(key, [])), "after_rows": len(right.get(key, []))}
                       for key in sorted(set(left) | set(right))}}


def failure_reason(run, raw_reply):
    if raw_reply and raw_reply.get("isError"):
        return "mcp_error_response"
    if (run / "response.json").exists():
        return "evaluation_incomplete_after_mcp_response"
    if (run / "calls.json").exists():
        return "product_attempt_without_complete_response"
    return "run_initialization_incomplete"


def export_run(run, destination, documents, helper):
    config = read(run / "run-config.json") if (run / "run-config.json").exists() else {}
    calls = read(run / "calls.json") if (run / "calls.json").exists() else {}
    summary = read(run / "summary.json") if (run / "summary.json").exists() else None
    raw_reply = read(run / "response.json") if (run / "response.json").exists() else None
    metadata = {key: config[key] for key in ("question", "case", "mode", "profile", "observe",
                "oracle_sha256", "harness_sha256", "contextual_relevance_sha256") if key in config}
    metadata.setdefault("profile", ("compact" if config["environment"].get("DOCATLAS_MCP_COMPACT_TEXT") == "1"
                                    else "canonical") if "environment" in config else "unknown")
    public_summary = {key: summary[key] for key in SUMMARY_FIELDS if key in summary} if summary else {
        **metadata, "calls": calls, "failure_reason": failure_reason(run, raw_reply)}
    public_summary.update(run_status="COMPLETE" if summary else "FAILED", recorded_configuration=metadata,
                          state_proof=state_proof(run))
    if summary and summary["calls"] != calls:
        raise ValueError("Summary and original call ledger differ")
    if summary and summary.get("source_and_index_unchanged") and public_summary["state_proof"]["logical_equal"] is not True:
        raise ValueError("Recorded index state does not support unchanged-state claim")
    delivered = []
    if raw_reply and not raw_reply.get("isError"):
        if len(raw_reply.get("content", [])) != 1 or raw_reply["content"][0].get("type") != "text":
            raise ValueError("Unexpected saved MCP representation")
        text = raw_reply["content"][0]["text"]
        if (run / "wire.txt").exists() and text != (run / "wire.txt").read_text(encoding="utf-8"):
            raise ValueError("Raw receipt and wire differ")
        delivered = source_rows(helper.source_rows(json.loads(text)), documents)
        public_summary["raw_wire_sha256"] = sha(text.encode())
    events = [json.loads(line) for line in (run / "observation.jsonl").read_text().splitlines()] if (run / "observation.jsonl").exists() else []
    acquisitions, selections, semantics = observation_exports(events, documents)
    if summary and sha(encode(stable(delivered))) != summary["delivered_rows_sha256"]:
        raise ValueError("Export changed delivered source rows")
    raw_files = {name: {"sha256": sha((run / name).read_bytes()), "bytes": (run / name).stat().st_size}
                 for name in RAW_NAMES if (run / name).exists()}
    inspect_public(public_summary)
    write(destination / "summary.json", public_summary)
    write(destination / "delivered.json.gz", delivered)
    write(destination / "acquisition.json.gz", acquisitions)
    write(destination / "selection.json.gz", selections)
    if semantics:
        write(destination / "semantic.json.gz", semantics)
    return {"name": run.name, "status": public_summary["run_status"], "calls": calls,
            "raw_artifacts": raw_files, "has_semantic_receipt": bool(semantics)}


def provenance(args):
    result = {}
    if args.installed_provenance:
        raw = read(args.installed_provenance)
        checked = []
        for item in raw.get("checks", []):
            checked.append({"path": relative(item["path"]), **{
                key: item[key] for key in ("sha256", "installed_sha256", "equal")}})
        result["installed"] = {"files": raw["files"], "python_files": raw["python_files"],
            "packages": raw["packages"], "mismatch_count": len(raw["mismatches"]), "checks": checked,
            "raw_provenance_sha256": sha(args.installed_provenance.read_bytes())}
    if args.asset_provenance:
        raw = read(args.asset_provenance)
        result["model_assets"] = {key: raw[key] for key in ("model_id", "revision", "status")}
        result["model_assets"]["assets"] = {relative(name): {key: record[key] for key in ("sha256", "bytes")}
                                            for name, record in raw["assets"].items()}
        result["model_assets"]["raw_provenance_sha256"] = sha(args.asset_provenance.read_bytes())
    if args.wheel:
        result["wheel"] = {"filename": args.wheel.name, "bytes": args.wheel.stat().st_size,
                           "sha256": sha(args.wheel.read_bytes())}
    inspect_public(result)
    return result


def verify(directory):
    """Validate public files/source facts without private raw or model assets."""
    manifest = read(directory / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        path = directory / relative(name)
        if sha(path.read_bytes()) != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            raise ValueError("Artifact checksum mismatch: " + name)
        inspect_public(read(path))
    source_manifest = read(directory / "source-manifest.json")
    documents = {}
    for name, expected in source_manifest["files"].items():
        path = REPO / relative(name)
        if sha(path.read_bytes()) != expected:
            raise ValueError("Repository source differs from frozen manifest: " + name)
        if name != "docatlas.project-docs.yaml":
            documents[name] = path.read_text(encoding="utf-8")
    oracle = read(HERE / "oracle.json")
    results, calls = [], {}
    for record in manifest["runs"]:
        run = directory / relative(record["name"])
        summary, delivered = read(run / "summary.json"), read(run / "delivered.json.gz")
        source_rows(delivered, documents)
        if record["calls"] != summary["calls"] or record["status"] != summary["run_status"]:
            raise ValueError("Manifest run ledger or status differs from public summary")
        for key, count in record["calls"].items():
            if type(count) is not int or count < 0:
                raise ValueError("Invalid original call ledger")
            calls[key] = calls.get(key, 0) + count
        if summary["run_status"] != "COMPLETE":
            results.append({"run": record["name"], "status": "FAILED", "facts": None})
            continue
        if summary["oracle_sha256"] != sha((HERE / "oracle.json").read_bytes()):
            raise ValueError("Frozen oracle changed")
        if sha(encode(stable(delivered))) != summary["delivered_rows_sha256"]:
            raise ValueError("Stable delivered row hash mismatch")
        if summary["source_rows"] != len(delivered):
            raise ValueError("Summary source count differs from exported delivered rows")
        proof = summary["state_proof"]
        if summary.get("source_and_index_unchanged") and (
            proof.get("logical_equal") is not True or proof.get("before_sha256") != proof.get("after_sha256")
            or any(count["before_rows"] != count["after_rows"] for count in proof.get("tables", {}).values())
        ):
            raise ValueError("Public state proof contradicts unchanged-state claim")
        selected_case = oracle if summary["case"] == "Q6" else oracle["regressions"][summary["case"]]
        if selected_case["question"] != summary["question"]:
            raise ValueError("Question differs from frozen case")
        covered = {path: bytearray(len(body)) for path, body in documents.items()}
        for row in delivered:
            path, start, end, snippet = row["path_or_url"], row["line_start"], row["line_end"], row["snippet"]
            lines = documents[path].splitlines(keepends=True)
            offset = sum(map(len, lines[:start - 1])) + "".join(lines[start - 1:end]).index(snippet)
            covered[path][offset:offset + len(snippet)] = b"\1" * len(snippet)
        facts = []
        for fact in selected_case["facts"]:
            start = documents[fact["path"]].index(fact["quote"])
            facts.append({"id": fact["id"], "delivered": all(covered[fact["path"]][start:start + len(fact["quote"])])})
        if facts != summary["facts"] or sum(f["delivered"] for f in facts) != summary["delivered_facts"]:
            raise ValueError("Public source facts disagree with summary")
        selections = read(run / "selection.json.gz")
        if len(selections) != len(summary["observation"]["selections"]):
            raise ValueError("Selection observation count differs from summary")
        for index, selection in enumerate(selections):
            source_rows(selection["checked_sources"], documents)
            expected = summary["observation"]["selections"][index]
            if (sha(encode(stable(selection["checked_sources"]))) != expected["ordered_pool_sha256"]
                or len(selection["checked_sources"]) != expected["checked_rows"]
                or selection["query_plan_sha256"] != expected["query_plan_sha256"]):
                raise ValueError("Checked pool hash mismatch")
        acquisitions = read(run / "acquisition.json.gz")
        if len(acquisitions) != len(summary["observation"]["acquisitions"]):
            raise ValueError("Acquisition observation count differs from summary")
        for index, acquisition in enumerate(acquisitions):
            rows = [{key: row[key] for key in ("rank", "text_sha256", "score", "path")}
                    for row in acquisition["rows"]]
            expected = summary["observation"]["acquisitions"][index]
            if (len(rows) != expected["count"] or sha(encode(rows)) != expected["ordered_pool_sha256"]
                or acquisition["query"] != expected["query"]):
                raise ValueError("Acquisition pool hash mismatch")
        if (run / "semantic.json.gz").exists():
            for receipt in read(run / "semantic.json.gz"):
                for row in receipt.get("rows", []):
                    text = documents[row["path"]]
                    if sha(text.encode()) != row["source_sha256"]:
                        raise ValueError("Semantic source hash mismatch")
                    for span in [row["body"], *row["available_context_spans"], *row["context_spans"]]:
                        fragment = text[span["char_start"]:span["char_end"]]
                        if sha(fragment.encode()) != span["sha256"]:
                            raise ValueError("Semantic structural span mismatch")
        results.append({"run": record["name"], "status": "VERIFIED_PUBLIC_SOURCE_FACTS",
                        "facts": summary["delivered_facts"], "rows": len(delivered)})
    if calls != manifest["calls"]:
        raise ValueError("Aggregate original calls differ")
    return {"runs": results, "calls": calls, "raw_mcp_authenticity": "requires_retained_private_raw",
            "live_source_authorization": "recorded_runtime_proof_not_reexecuted",
            "model_execution": "not_reexecuted"}


def export(args):
    import yaml
    spec = importlib.util.spec_from_file_location("q6_export_helpers", REPO / "eval/opencode_compat/installed_stdio.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    root, out = args.runs.resolve(), args.out.resolve()
    if out.exists():
        raise FileExistsError("Output already exists; refusing to overwrite")
    names = args.run or sorted(path.name for path in root.iterdir() if path.is_dir())
    if not names or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."} for name in names):
        raise ValueError("Expected explicit safe run directory names")
    runs = [root / name for name in names]
    manifests = [read(run / "source-manifest.json") for run in runs if (run / "source-manifest.json").exists()]
    if not manifests or any(value != manifests[0] for value in manifests):
        raise ValueError("Runs do not share one frozen corpus")
    documents = {name: (REPO / relative(name)).read_text(encoding="utf-8")
                 for name in manifests[0] if name != "docatlas.project-docs.yaml"}
    for name, expected in manifests[0].items():
        if sha((REPO / relative(name)).read_bytes()) != expected:
            raise ValueError("Repository source changed since measurement")
    catalog = yaml.safe_load((REPO / "docatlas.project-docs.yaml").read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".q6-export-", dir=out.parent))
    try:
        write(staging / "source-manifest.json", {"files": manifests[0], "catalog_members": catalog["documents"]})
        write(staging / "provenance.json", provenance(args))
        records = [export_run(run, staging / run.name, documents, helper) for run in runs]
        counts = {}
        for record in records:
            for key, value in record["calls"].items():
                counts[key] = counts.get(key, 0) + value
        artifacts = {path.relative_to(staging).as_posix(): {"sha256": sha(path.read_bytes()), "bytes": path.stat().st_size}
                     for path in sorted(staging.rglob("*")) if path.is_file()}
        manifest = {"schema": "q6-public-review-evidence-v1", "runs": records, "calls": counts, "artifacts": artifacts,
            "tool_sources": {name: sha((HERE / name).read_bytes()) for name in
                             ("probe.py", "oracle.json", "contextual_relevance.py", "export_results.py")},
            "tool_sources_role": "Recorded export provenance; future verification checks frozen source/oracle bytes, not the current exporter revision.",
            "raw_only_boundary": ["Full MCP responses and live source/continuation capabilities",
                "Private runtime configuration and absolute executable/package paths",
                "Full source admission snapshots and native capability objects",
                "Complete indexed database state and raw diagnostic streams"],
            "verification_limits": "Public files reproduce source-fact scoring and exact spans; raw authenticity and live admission require the retained runtime receipts."}
        inspect_public(manifest)
        write(staging / "manifest.json", manifest)
        verified = verify(staging)
        if out.exists():
            raise FileExistsError("Output appeared during export; refusing to overwrite")
        os.rename(staging, out)
        return verified
    except BaseException:
        shutil.rmtree(staging)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--run", action="append", help="Export only this named run; repeat for an offline smoke")
    parser.add_argument("--installed-provenance", type=Path)
    parser.add_argument("--asset-provenance", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--verify", type=Path, help="Verify already exported evidence with stdlib and repository sources")
    args = parser.parse_args()
    if args.verify:
        result = verify(args.verify.resolve())
    else:
        if args.runs is None or args.out is None:
            parser.error("--runs and --out are required for export")
        result = export(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
