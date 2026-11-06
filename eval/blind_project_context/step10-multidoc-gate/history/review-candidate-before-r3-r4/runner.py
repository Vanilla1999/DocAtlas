"""Project-level public gate. Commands require an explicitly frozen manifest.

No automatic freeze, validation chaining, model mocks or monkeypatch caches.
Calibration final-pass replay is real inference and is counted again.
"""
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
TREE = ROOT.parents[2]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def verify_manifest(path):
    manifest = json.loads(path.read_text())
    if manifest.get("status") != "FROZEN_APPROVED_FOR_INFERENCE":
        raise ValueError("gate_manifest_not_frozen_or_approved")
    for relative, expected in manifest["files"].items():
        if digest((TREE / relative).read_bytes()) != expected:
            raise ValueError("frozen_input_changed:" + relative)
    return manifest, digest(path.read_bytes())


def database_digest(path):
    with sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True) as db:
        return digest("\n".join(db.iterdump()).encode())


def inventory(project, labels):
    sources = {path: (ROOT / project["root"] / path).read_bytes().decode("utf-8")
               for path in project["project_documents"]}
    units = {}
    for row in labels:
        if row["scope"] != "project":
            continue
        raw = sources[row["path"]]
        lines = raw.splitlines(keepends=True)
        start = sum(map(len, lines[:row["heading_line"] - 1]))
        body_start = start + len(lines[row["heading_line"] - 1])
        end = sum(map(len, lines[:row["line_end"]]))
        assert raw[body_start:end] == row["own_text"]
        assert digest(raw.encode()) == row["source_sha256"]
        units[row["key"]] = {**row, "char_start": start, "body_char_start": body_start,
                              "char_end": end, "whole_text": raw[start:end]}
    # The authored fixtures intentionally contain no footnote/reference-definition
    # syntax; offline fitting closes ancestors only. Inline anchors do not add
    # bodies in structural v2. New fixture syntax requires evaluator review.
    assert all("[^" not in raw and not re.search(r"(?m)^ {0,3}\[[^\]\n]+\]:", raw) for raw in sources.values())
    for key, unit in units.items():
        earlier = sorted((u for u in units.values() if u["path"] == unit["path"] and
                          u["heading_line"] < unit["heading_line"]), key=lambda u: u["heading_line"], reverse=True)
        level, ancestors = unit["heading_level"], []
        for other in earlier:
            if other["heading_level"] < level:
                ancestors.append(other["key"])
                level = other["heading_level"]
        unit["ancestors"] = ancestors
    return sources, units


def source_tokens(selected, units, sources, count):
    """Unique original character intervals, merge adjacency per source; no gaps joined."""
    total = 0
    for path, raw in sources.items():
        intervals = sorted((units[k]["char_start"], units[k]["char_end"]) for k in selected if units[k]["path"] == path)
        merged = []
        for a, b in intervals:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        total += sum(count(raw[a:b].encode()) for a, b in merged)
    return total


def coverage(selected, task, units, sources, count):
    required = set(task["direct"]) | set(task["structural"])
    return {"missing_required_units": sorted(required - selected),
            "missing_facts": [[key, quote] for key, quote in task["facts"]
                              if key not in selected or quote not in units[key]["whole_text"]],
            "hard_negatives": sorted(set(task["hard_negatives"]) & selected),
            "optional_units": sorted(k for k in selected if units[k]["role"].startswith("optional")),
            "unlabelled_units": sorted(k for k in selected if units[k]["role"] == "unlabelled"),
            "selected_units": sorted(selected), "source_rows": len(selected),
            "delivered_source_tokens": source_tokens(selected, units, sources, count),
            "allowed_source_tokens": sum(count(raw.encode()) for raw in sources.values()),
            "role_source_tokens": {role: source_tokens({k for k in selected if units[k]["role"] == role}, units, sources, count)
                                   for role in ("direct", "structural", "optional_support", "optional_context", "negative", "unlabelled")}}


def packet_check(packet, observation, task, project, labels, count, expected_project_identity):
    sources, units = inventory(project, labels)
    assert packet.get("kind") == "docs_context", packet
    selection = packet.get("source_selection", {})
    assert selection.get("scan_complete") and observation["receipt"]["status"] == "complete", packet
    assert not selection.get("closure", {}).get("incomplete_dependencies"), packet
    assert packet.get("reason_code") not in ("scan_incomplete", "context_emergency_stop")
    selected, order = set(), []
    for row in packet.get("sources", []):
        path = row["path_or_url"]
        assert path in sources and row["scope"] == "project"
        assert row["authority"] == "source_of_truth" and row["version_binding"] == "unversioned"
        assert row["project_identity"] == expected_project_identity and row["source_uri"] and row["evidence_id"]
        matches = [k for k, u in units.items() if u["path"] == path and u["heading_line"] == row["line_start"]
                   and u["line_end"] == row["line_end"] and u["whole_text"] == row["snippet"]]
        assert len(matches) == 1 and matches[0] not in selected, row
        key = matches[0]
        selected.add(key)
        order.append(key)
        material = {"path": path, "section": row.get("section"), "content": units[key]["whole_text"],
                    "snippet": units[key]["whole_text"], "version": None}
        assert digest(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) == row["content_sha256"]
    for path in sources:
        same_doc = [units[k]["heading_line"] for k in order if units[k]["path"] == path]
        assert same_doc == sorted(same_doc), "source order changed"
    scores = {}
    for score in observation["scores"]:
        matches = [k for k, u in units.items() if u["path"] == score["path"] and
                   u["char_start"] == score["char_start"] and u["char_end"] == score["char_end"] and
                   u["body_char_start"] == score["body_char_start"]]
        assert len(matches) == 1 and matches[0] not in scores, score
        assert score["source_sha256"].removeprefix("sha256:") == units[matches[0]]["source_sha256"]
        assert json.loads(score["source_identity"])["candidate"]["project_identity"] == expected_project_identity
        assert math.isfinite(score["score"])
        scores[matches[0]] = score["score"]
    assert scores.keys() == units.keys(), "scan inventory incomplete or foreign source scored"
    if task.get("explicit_full_section"):
        descendants = [k for k, u in units.items() if task["explicit_full_section"] in u["ancestors"]]
        assert set(descendants) <= set(task["direct"]) | set(task["structural"])
        # Coverage failure is reported, not fixed with subtree fallback.
        if set(descendants) <= selected:
            assert [units[k]["heading_line"] for k in order if k in descendants] == sorted(units[k]["heading_line"] for k in descendants)
    return coverage(selected, task, units, sources, count), scores


def gates(results):
    answerable = [r for r in results if not r["no_answer"]]
    denominator = sum(r["allowed_source_tokens"] for r in answerable)
    numerator = sum(r["delivered_source_tokens"] for r in answerable)
    return {"required_pass": all(not r["missing_required_units"] and not r["missing_facts"] for r in results),
            "no_answer_pass": all(r["source_rows"] == 0 for r in results if r["no_answer"]),
            "hard_negative_pass": all(not r["hard_negatives"] for r in results),
            "reduction_pass": bool(denominator and numerator * 2 <= denominator),
            "source_tokens_numerator": numerator, "source_tokens_denominator": denominator,
            "source_reduction": 1 - numerator / denominator if denominator else None}


def run(args):
    if not __debug__:
        raise ValueError("gate_requires_assertions_enabled")
    manifest, manifest_sha = verify_manifest(args.manifest)
    from eval.evidence_quality_v2 import runtime
    from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
    from docmancer.docs.application.minimal_context_selection import observe_minimal_context
    from docmancer.docs.application import context_evidence_scoring as scorer
    from docmancer.docs.application.projection_tokenizer import projection_token_count as count
    from docmancer.docs.application.standalone_text_view import render_standalone_text
    import yaml
    assert manifest["contract_sha256"] == scorer.CONTRACT_SHA256
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    projects = json.loads((ROOT / "projects.json").read_text())
    tasks = json.loads((ROOT / "tasks.json").read_text())
    labels = {r["task_id"]: r["units"] for r in json.loads((ROOT / "draft-labels.json").read_text())}
    counts = {"public_prepares": 0, "public_queries": 0, "resource_reads": 0,
              "model_forwards": 0, "model_input_tokens": 0, "score_cache_hits": 0,
              "runtime_cache_hits": 0, "model_loads": 0, "inference_seconds": 0.0,
              "scoring_total_seconds": 0.0, "peak_vram_allocated_bytes": 0,
              "peak_vram_reserved_bytes": 0}
    all_records, diagnostic_scores, prepared = [], {}, {}

    def phase(split, name, policy_path=None):
        records = []
        for project in [p for p in projects if p["split"] == split]:
            group = [t for t in tasks if t["project"] == project["id"]]
            dest = args.out / name / project["id"]
            # Keep native source identity (including absolute root/generation)
            # identical between diagnostic scoring and final policy replay.
            fixture = args.out / "fixtures" / project["id"]
            source_root = fixture / "project"
            names = project["project_documents"] + [d["path"] for d in project["module_documents"]]
            originals = {p: (ROOT / project["root"] / p).read_bytes() for p in names}
            if project["id"] not in prepared:
                runtime.write_project(source_root, {p: raw.decode() for p, raw in originals.items()})
                catalog_path = source_root / "docatlas.project-docs.yaml"
                catalog = yaml.safe_load(catalog_path.read_text())
                modules = {d["path"]: d for d in project["module_documents"]}
                for entry in catalog["documents"]:
                    if entry["path"] in modules:
                        entry.update(scope="module", module_path=modules[entry["path"]]["module_path"])
                catalog_path.write_text(yaml.safe_dump(catalog))
            watched = {p.relative_to(source_root).as_posix(): digest(p.read_bytes()) for p in source_root.rglob("*") if p.is_file()}
            with runtime.isolated_service(fixture / "state") as (service, config):
                os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="1", DOCATLAS_CONTEXT_COMPRESSION="off",
                                  DOCATLAS_MINIMAL_CONTEXT_RECIPE=scorer.RECIPE,
                                  DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH=str(args.model.resolve()))
                if policy_path:
                    os.environ["DOCATLAS_MINIMAL_CONTEXT_POLICY"] = str(policy_path.resolve())
                else:
                    os.environ.pop("DOCATLAS_MINIMAL_CONTEXT_POLICY", None)
                if project["id"] not in prepared:
                    prepared[project["id"]] = runtime.index_project(service, config, source_root)
                    counts["public_prepares"] += 1
                inventory_receipt = prepared[project["id"]]
                save(dest / "prepare.json", inventory_receipt)
                assert not inventory_receipt["excluded_or_failed_paths"] and not inventory_receipt["unexpected_paths"]
                before_db = database_digest(config.index.db_path)
                references_checked = False
                for task in group:
                    tick = time.perf_counter()
                    with observe_minimal_context() as observed:
                        packet = call_docs_tool_payload("get_docs_context", {
                            "question": task["question"], "project_path": str(source_root), "scope": "project"}, service)
                    counts["public_queries"] += 1
                    save(dest / (task["id"] + ".json"), {"packet": packet, "observations": observed})
                    # Preserve failure counters before interpreting product success.
                    receipt = observed[0]["receipt"] if observed else packet.get("source_selection", {}).get("receipt", {})
                    for key in ("model_forwards", "model_input_tokens", "score_cache_hits",
                                "runtime_cache_hits", "model_loads", "inference_seconds"):
                        counts[key] += receipt.get(key, 0)
                    counts["scoring_total_seconds"] += receipt.get("total_seconds", 0)
                    for key in ("peak_vram_allocated_bytes", "peak_vram_reserved_bytes"):
                        counts[key] = max(counts[key], receipt.get(key, 0))
                    save(args.out / "counts.json", counts)
                    assert len(observed) == 1, packet
                    expected_policy = digest(policy_path.read_bytes()) if policy_path else "diagnostic-unverified"
                    assert observed[0]["policy_sha256"] == expected_policy
                    checked, scores = packet_check(packet, observed[0], task, project, labels[task["id"]], count,
                                                   "local:" + digest(str(source_root.resolve()).encode()))
                    rendered = render_standalone_text(packet)
                    record = {"id": task["id"], "phase": name, "split": split,
                              "no_answer": bool(task.get("no_answer")), **checked,
                              "seconds": time.perf_counter() - tick, "scorer_receipt": receipt,
                              "packet_json_tokens": count(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode()),
                              "supported_rendering_tokens": count(rendered.text.encode()) if rendered.text else None,
                              "actual_mcp_wire_tokens": None, "actual_client_model_visible_tokens": None}
                    records.append(record)
                    all_records.append(record)
                    if name == "calibration-diagnostic":
                        diagnostic_scores[task["id"]] = scores
                    if policy_path and packet.get("sources") and not references_checked:
                        for row in {r["source_uri"]: r for r in (packet["sources"][0], packet["sources"][-1])}.values():
                            value = json.loads(read_docs_resource(row["source_uri"], service)["text"])
                            replay = json.loads(read_docs_resource(row["source_uri"], service)["text"])
                            counts["resource_reads"] += 2
                            save(dest / (task["id"] + "-" + row["evidence_id"] + "-resource.json"), {"value": value, "replay": replay})
                            assert replay.get("reason_code") == "unknown_or_expired_reference"
                            if "snippet" in value:
                                assert value["path"] in project["project_documents"]
                                raw = originals[value["path"]].decode()
                                assert value["snippet"] == "".join(raw.splitlines(keepends=True)[value["line_start"] - 1:value["line_end"]])
                                assert value["content_sha256"].removeprefix("sha256:") == digest(raw.encode())
                                assert value["project_identity"] == row["project_identity"]
                            else:
                                assert value == {"status": "complete", "reason_code": "end_of_source"}
                        references_checked = True
                    assert database_digest(config.index.db_path) == before_db
                    assert watched == {p.relative_to(source_root).as_posix(): digest(p.read_bytes()) for p in source_root.rglob("*") if p.is_file()}
                    save(args.out / "results.json", all_records)
                    save(args.out / "counts.json", counts)
                scorer.verify_assets(str(args.model.resolve()))
        return records

    try:
        if args.command == "calibration":
            phase("calibration", "calibration-diagnostic")
            calibration_tasks = [t for t in tasks if any(p["id"] == t["project"] and p["split"] == "calibration" for p in projects)]
            points = sorted({score for scores in diagnostic_scores.values() for score in scores.values()}, reverse=True)
            trials, best = [], None
            for threshold in [math.nextafter(points[0], math.inf), *points]:
                predicted = []
                for task in calibration_tasks:
                    project = next(p for p in projects if p["id"] == task["project"])
                    sources, units = inventory(project, labels[task["id"]])
                    seeds = {k for k, score in diagnostic_scores[task["id"]].items() if score >= threshold}
                    selected = seeds | {a for key in seeds for a in units[key]["ancestors"]}
                    predicted.append({"id": task["id"], "no_answer": bool(task.get("no_answer")),
                                      **coverage(selected, task, units, sources, count)})
                result = gates(predicted)
                trials.append({"threshold": threshold, "empty_boundary": threshold > points[0], "gates": result, "results": predicted})
                if threshold <= points[0] and result["required_pass"]:
                    best = trials[-1]
                    break
            save(args.out / "breakpoints.json", trials)
            if best is None or not all(best["gates"][key] for key in ("required_pass", "no_answer_pass", "hard_negative_pass", "reduction_pass")):
                save(args.out / "summary.json", {"status": "FAIL", "stage": "calibration_fit", "best": best, "counts": counts})
                return
            policy = {"schema_version": 3, "recipe": scorer.RECIPE, "model_id": scorer.MODEL_ID,
                      "model_revision": scorer.REVISION, "structural_recipe": scorer.STRUCTURAL_RECIPE,
                      "lanes": "exact_original_only", "contract_sha256": scorer.CONTRACT_SHA256,
                      "calibration_recipe": scorer.CALIBRATION_RECIPE, "calibration_sha256": manifest_sha,
                      "threshold": best["threshold"]}
            policy_path = args.out / "policy.json"
            save(policy_path, policy)
            final = phase("calibration", "calibration-final", policy_path)
            verdict = gates(final)
            prediction = {r["id"]: r["selected_units"] for r in best["results"]}
            assert all(r["selected_units"] == prediction[r["id"]] for r in final), "offline closure fit disagrees with real final delivery"
        else:
            if not args.calibration or not args.validation_authorization:
                raise ValueError("validation_requires_calibration_directory_and_separate_permission")
            summary = json.loads((args.calibration / "summary.json").read_text())
            policy_path = args.calibration / "policy.json"
            assert summary["status"] == "PASS" and summary["phase"] == "calibration" and summary["manifest_sha256"] == manifest_sha
            assert digest(policy_path.read_bytes()) == summary["policy_sha256"]
            authorization = json.loads(args.validation_authorization.read_text())
            assert authorization["status"] == "PARENT_APPROVED_VALIDATION"
            assert authorization["manifest_sha256"] == manifest_sha
            assert authorization["policy_sha256"] == summary["policy_sha256"]
            assert authorization["calibration_summary_sha256"] == digest((args.calibration / "summary.json").read_bytes())
            final = phase("validation", "validation", policy_path)
            verdict = gates(final)
        save(args.out / "summary.json", {"status": "PASS" if all(verdict[k] for k in ("required_pass", "no_answer_pass", "hard_negative_pass", "reduction_pass")) else "FAIL",
             "phase": args.command, "manifest_sha256": manifest_sha, "policy_sha256": digest(policy_path.read_bytes()),
             "gates": verdict, "counts": counts, "boundary": "public in-process, not installed/client/Terra"})
    except Exception as exc:
        save(args.out / "failure.json", {"status": "ERROR_NOT_PASS", "error_type": type(exc).__name__, "error": str(exc), "counts": counts})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("calibration", "validation"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--validation-authorization", type=Path)
    run(parser.parse_args())
