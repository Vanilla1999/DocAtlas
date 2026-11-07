#!/usr/bin/env python3
"""Fresh v2 body-gate calibration through real public prepare/query calls.

Run with the pinned supported Python environment and PYTHONPATH=<repo>.
Commands: freeze (once, before inference), verify, run --work-dir <new path>.
No labels or expected facts enter the production service or prepared project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time

ROOT = Path(__file__).resolve().parent
RECIPE = {
    "schema_version": 1,
    "recipe": "complete-own-body-gated-maxp-v2",
    "model_revision": "1427fd652930e4ba29e8149678df786c240d8825",
    "structural_recipe": "minimal-structure-v1",
    "lanes": "original_translation_max",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def own_units(text):
    """Independent fixture-only ATX inventory; not a production parser oracle.

    These authored sources intentionally use simple ATX headings and paragraphs.
    Both heading and exact own-body boundaries are frozen, allowing a diagnostic
    identity to be matched without consulting model outputs to infer usefulness.
    """
    lines = text.splitlines()
    headings = [(i, match.group(2)) for i, line in enumerate(lines)
                if (match := re.fullmatch(r"(#{1,6}) (.+)", line))]
    result = []
    for n, (start, heading) in enumerate(headings):
        stop = headings[n + 1][0] if n + 1 < len(headings) else len(lines)
        body = [i for i in range(start + 1, stop) if lines[i].strip()]
        if body:
            result.append({"heading": heading, "heading_line": start + 1,
                           "line_start": body[0] + 1, "line_end": body[-1] + 1,
                           "own_text": "\n".join(lines[body[0]:body[-1] + 1])})
    return result


def freeze():
    if (ROOT / "manifest.json").exists():
        raise ValueError("Already frozen; do not rewrite a calibration after inference")
    tasks = json.loads((ROOT / "tasks.json").read_text())
    labels = []
    families = {}
    for task in tasks:
        families.setdefault(task["family"], set()).add(task["split"])
        document = ROOT / task["split"] / task["document"]
        text = document.read_text()
        units = own_units(text)
        if not set(task["useful"]) <= {u["heading"] for u in units}:
            raise ValueError("Unknown useful heading")
        if not all(fact in text for fact in task["facts"]):
            raise ValueError("Expected fact absent from independently authored source")
        labels.append({"task_id": task["id"], "document_sha256": digest(document.read_bytes()),
                       "units": [{**unit, "useful": unit["heading"] in task["useful"]}
                                 for unit in units]})
    if any(len(splits) != 1 for splits in families.values()):
        raise ValueError("Family leakage across calibration and validation")
    save(ROOT / "labels.json", labels)
    recipe = json.loads((ROOT / "recipe.json").read_text())
    if any(recipe.get(k) != v for k, v in RECIPE.items()):
        raise ValueError("Authored recipe must agree with public v2 interface")
    paths = [ROOT / "tasks.json", ROOT / "labels.json", ROOT / "recipe.json", ROOT / "README.md"]
    paths += sorted(ROOT.glob("calibration/*.md")) + sorted(ROOT.glob("validation/*.md"))
    save(ROOT / "manifest.json", {
        "schema_version": 1, "frozen_before_inference": True,
        "provenance": "Independent agent-authored fictional manuals; not an external benchmark",
        "files": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in paths},
        "split_families": {k: sorted(v) for k, v in families.items()},
        "task_count": len(tasks), "labeled_units": sum(len(x["units"]) for x in labels),
    })
    return verify()


def verify():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")
    if any(json.loads((ROOT / "recipe.json").read_text()).get(k) != v for k, v in RECIPE.items()):
        raise ValueError("Scoring recipe changed; new independent version required")
    return {"manifest_sha256": digest((ROOT / "manifest.json").read_bytes()),
            "tasks": manifest["task_count"], "labeled_units": manifest["labeled_units"]}


def db_digest(path):
    # Logical state includes all persisted rows and schema, not WAL file timing.
    with sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True) as db:
        return digest("\n".join(db.iterdump()).encode())


def normalize_path(value, project):
    path = Path(value)
    return path.relative_to(project).as_posix() if path.is_absolute() else path.as_posix()


def match_scores(receipt, units, document, project, text):
    """Require exhaustive public score-to-source binding, fail closed on ambiguity."""
    scores = receipt.get("scores")
    if not isinstance(scores, list):
        raise ValueError("Same-call observer receipt does not expose scores")
    matches = {}
    for score in scores:
        if not isinstance(score.get("score"), (int, float)) or not math.isfinite(score["score"]):
            raise ValueError("Nonfinite or missing public raw score")
        for key in ("contextual_score", "own_body_score"):
            if not isinstance(score.get(key), (int, float)) or not math.isfinite(score[key]):
                raise ValueError("V2 observer must expose both finite component scores")
        if score["score"] != min(score["contextual_score"], score["own_body_score"]):
            raise ValueError("V2 score does not implement the frozen minimum gate")
        path = score.get("source_path") or score.get("path_or_url") or score.get("path")
        if not path or normalize_path(path, project) != document:
            raise ValueError("Missing/foreign public score source_path")
        start, end = score.get("line_start"), score.get("line_end")
        if start is None and isinstance(score.get("char_start"), int) and isinstance(score.get("char_end"), int):
            a, b = score["char_start"], score["char_end"]
            if not 0 <= a < b <= len(text):
                raise ValueError("Invalid diagnostic character offsets")
            start = text.count("\n", 0, a) + 1
            end = text.count("\n", 0, b - 1) + 1
        candidates = [unit for unit in units
                      if isinstance(start, int) and isinstance(end, int)
                      and unit["heading_line"] <= start <= unit["line_start"]
                      and unit["line_end"] <= end
                      and not any(start <= other["heading_line"] <= end
                                  for other in units if other is not unit)]
        if len(candidates) != 1 or candidates[0]["heading"] in matches:
            raise ValueError(f"Public own-unit coordinates are ambiguous: {score}")
        matches[candidates[0]["heading"]] = score
    if set(matches) != {unit["heading"] for unit in units}:
        raise ValueError("Public pipeline did not score every independently inventoried own-body unit")
    return matches


def evaluate_packet(payload, units, task, project, text, threshold, diagnostic=None):
    packet = payload
    if packet.get("kind") != "docs_context":
        raise ValueError(f"Public query did not deliver docs_context: {packet}")
    selection = packet.get("source_selection", {})
    if not selection.get("scan_complete"):
        raise ValueError(f"Public semantic scan was not complete: {selection}")
    if threshold is not None and selection.get("calibration_status") != "empirical":
        raise ValueError("Validation query did not use the calibrated policy")
    receipt = diagnostic if diagnostic is not None else selection.get("minimal_semantic", {})
    scores = match_scores(receipt, units, task["document"], project, text)
    scoring = receipt.get("receipt", {})
    if scoring.get("status") != "complete" or scoring.get("recipe") != RECIPE["recipe"]:
        raise ValueError("Diagnostic scoring did not complete the frozen recipe")
    if scoring.get("aggregation") != "min_contextual_and_own_body_max_raw_logit":
        raise ValueError("V2 observer reports a different aggregation")
    if "tail-ru" in task["id"] and not any(row.get("body_tokens", 0) > 512 for row in scores.values()):
        raise ValueError("Tail challenge did not reach beyond the physical model window")
    sources = packet.get("sources") or []
    snippets = []
    for source in sources:
        if normalize_path(source["path_or_url"], project) != task["document"]:
            raise ValueError("Foreign source in public packet")
        start, end = source["line_start"], source["line_end"]
        lines = text.splitlines(keepends=True)
        if not (type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)):
            raise ValueError("Invalid source coordinates")
        if not source["snippet"] or source["snippet"] not in "".join(lines[start-1:end]):
            raise ValueError("Delivered text is not verbatim source-span text")
        if source.get("scope") != "project" or source.get("authority") != "source_of_truth":
            raise ValueError("Wrong source scope/authority")
        if not source.get("project_identity") or not re.fullmatch(r"[0-9a-f]{64}", source.get("content_sha256", "")):
            raise ValueError("Missing checked source identity/fingerprint")
        snippets.append(source["snippet"])
    for reference in packet.get("read_next") or []:
        if normalize_path(reference["path"], project) != task["document"]:
            raise ValueError("Foreign source continuation")
        if reference.get("snapshot_sha256") != "sha256:" + digest(text.encode()):
            raise ValueError("Source continuation hash differs from frozen source bytes")
    missing_facts = [fact for fact in task["facts"] if not any(fact in snippet for snippet in snippets)]
    rows = [{"heading": unit["heading"], "useful": unit["useful"],
             "score": scores[unit["heading"]]["score"],
             "contextual_score": scores[unit["heading"]]["contextual_score"],
             "own_body_score": scores[unit["heading"]]["own_body_score"],
             "direct_keep": threshold is None or scores[unit["heading"]]["score"] >= threshold,
             "delivered": any(unit["own_text"] in snippet for snippet in snippets),
             "body_tokens": scores[unit["heading"]].get("body_tokens")}
            for unit in units]
    return {"id": task["id"], "split": task["split"], "units": rows,
            "missing_facts": missing_facts, "expected_facts": len(task["facts"]),
            "delivered_characters": sum(len(x) for x in snippets),
            "source_characters": len(text), "source_count": len(sources),
            "source_checks": "pass", "semantic_receipt": receipt}


def run(args):
    frozen = verify()  # Must finish before importing runtime/model code.
    from eval.evidence_quality_v2 import runtime
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
    from docmancer.docs.application.minimal_context_selection import observe_minimal_context
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    tasks = json.loads((ROOT / "tasks.json").read_text())
    labels = {row["task_id"]: row for row in json.loads((ROOT / "labels.json").read_text())}
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    save(work / "frozen-inputs.json", frozen)
    results = []
    public_queries = 0
    prepares = 0
    threshold = None
    policy_path = work / "policy.json"
    # Calibration diagnostics precede validation, which uses the immutable policy.
    for split in ("calibration", "validation"):
        selected = [task for task in tasks if task["split"] == split]
        for document in sorted({task["document"] for task in selected}):
            project = work / split / document.replace(".md", "") / "project"
            text = (ROOT / split / document).read_text()
            runtime.write_project(project, {document: text})
            with runtime.isolated_service(project.parent / "state") as (service, config):
                os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="1",
                                  DOCATLAS_EXPERIMENT_MINI_PATH=str(args.model_path.resolve()),
                                  DOCATLAS_MINIMAL_CONTEXT_RECIPE=RECIPE["recipe"])
                if split == "validation":
                    os.environ["DOCATLAS_MINIMAL_CONTEXT_POLICY"] = str(policy_path)
                inventory = runtime.index_project(service, config, project)
                prepares += 1
                save(project.parent / "prepare.json", inventory)
                if inventory["excluded_or_failed_paths"] or inventory["unexpected_paths"]:
                    raise ValueError("Public preparation did not commit exact fixture sources")
                if inventory["documents"] != [{**entry, "content_sha256": digest(text.encode())}
                                              for entry in inventory["documents"]]:
                    raise ValueError("Prepared document hash differs from frozen bytes")
                before = db_digest(inventory["storage_path"])
                for task in (t for t in selected if t["document"] == document):
                    arguments = {"question": task["question"], "project_path": str(project), "scope": "project"}
                    if task.get("search_question"):
                        arguments["search_question"] = task["search_question"]
                    tick = time.perf_counter()
                    # Observe the same real public call, including policy-mode
                    # validation. No diagnostic second query or model-visible scores.
                    with observe_minimal_context() as observations:
                        payload = call_docs_tool_payload("get_docs_context", arguments, service)
                    public_queries += 1
                    save(work / "packets" / (task["id"] + ".json"), payload)
                    save(work / "observations" / (task["id"] + ".json"), observations)
                    try:
                        if len(observations) != 1:
                            raise ValueError("Expected exactly one passive observation per public call")
                        diagnostic = observations[0]
                        if "minimal_semantic" in payload.get("source_selection", {}):
                            raise ValueError("Observer scores leaked into model-visible source_selection")
                        if split == "validation" and diagnostic.get("policy_sha256") != frozen_policy_digest:
                            raise ValueError("Observed validation did not use the frozen policy bytes")
                        result = evaluate_packet(payload, labels[task["id"]]["units"], task, project, text, threshold, diagnostic)
                    except Exception as exc:
                        save(work / "failure.json", {"task": task["id"], "error": str(exc),
                             "public_prepare_calls": prepares, "public_get_docs_context_calls": public_queries,
                             "frozen_manifest_sha256": frozen["manifest_sha256"]})
                        raise
                    result["seconds"] = time.perf_counter() - tick
                    result["serialized_utf8_bytes"] = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
                    result["serialized_json_tokens"] = projection_token_count(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
                    results.append(result)
                    save(work / "results.json", results)
                if db_digest(inventory["storage_path"]) != before:
                    raise ValueError("Read query changed persistent SQLite state")
                if (project / document).read_text() != text:
                    raise ValueError("Read query changed source bytes")
        if split == "calibration":
            positives = [unit["score"] for result in results for unit in result["units"] if unit["useful"]]
            if not positives:
                raise ValueError("No calibration positives")
            threshold = min(positives)
            save(policy_path, {**RECIPE, "threshold": threshold,
                               "calibration_sha256": frozen["manifest_sha256"],
                               "calibration_manifest_sha256": frozen["manifest_sha256"]})
            frozen_policy_digest = digest(policy_path.read_bytes())
    if digest(policy_path.read_bytes()) != frozen_policy_digest:
        raise ValueError("Policy changed during validation")
    summary = {**frozen, "policy_sha256": digest(policy_path.read_bytes()), "threshold": threshold,
               "public_prepare_calls": prepares, "public_get_docs_context_calls": public_queries,
               "boundary": "in-process public production prepare/query; real local pinned model; not installed stdio/client/answer-model",
               "splits": {}}
    for split in ("calibration", "validation"):
        cases = [row for row in results if row["split"] == split]
        units = [unit for row in cases for unit in row["units"]]
        summary["splits"][split] = {
            "tasks": len(cases), "labeled_units": len(units),
            "positive_units": sum(u["useful"] for u in units),
            "negative_units": sum(not u["useful"] for u in units),
            "missed_direct_positives": sum(u["useful"] and u["score"] < threshold for u in units),
            "false_positive_units": sum(not u["useful"] and u["score"] >= threshold for u in units),
            "delivered_negative_units": sum(not u["useful"] and u["delivered"] for u in units),
            "missed_delivered_positives": sum(u["useful"] and not u["delivered"] for u in units),
            "missing_facts": sum(len(row["missing_facts"]) for row in cases),
            "expected_facts": sum(row["expected_facts"] for row in cases),
            "noanswer_nonempty": sum(row["source_count"] > 0 for row in cases if not row["expected_facts"]),
            "noanswer_tasks": sum(not row["expected_facts"] for row in cases),
            "contextual_direct_positive_misses_at_frozen_v2_tau": sum(u["useful"] and u["contextual_score"] < threshold for u in units),
            "contextual_direct_false_positives_at_frozen_v2_tau": sum(not u["useful"] and u["contextual_score"] >= threshold for u in units),
            "gate_removed_false_positives_at_frozen_v2_tau": sum(not u["useful"] and u["contextual_score"] >= threshold and u["score"] < threshold for u in units),
            "gate_removed_positives_at_frozen_v2_tau": sum(u["useful"] and u["contextual_score"] >= threshold and u["score"] < threshold for u in units),
            "delivered_characters": sum(row["delivered_characters"] for row in cases),
            "source_characters": sum(row["source_characters"] for row in cases),
            "serialized_json_tokens": sum(row["serialized_json_tokens"] for row in cases),
            "seconds": sum(row["seconds"] for row in cases),
        }
    summary["validation_retention_pass"] = not any(summary["splits"]["validation"][key]
        for key in ("missed_direct_positives", "missed_delivered_positives", "missing_facts"))
    summary["limitation"] = "Small fresh authored synthetic set. Calibration packets are keep-all diagnostic, not filtered savings. Component-score comparisons use the frozen v2 threshold and are not separately calibrated v1 policy runs or a causal closure ablation. No conformal or external benchmark guarantee. False positives/no-answer noise reported even when retention passes."
    save(work / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "verify", "run"))
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--model-path", type=Path, default=Path("/tmp/opencode/step10-mini-assets"))
    args = parser.parse_args()
    if args.command == "run" and not args.work_dir:
        parser.error("run requires --work-dir (must not already exist)")
    print(json.dumps(freeze() if args.command == "freeze" else verify() if args.command == "verify" else run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
