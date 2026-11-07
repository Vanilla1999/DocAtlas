"""One authorized public C-T1/consume/replay/C-T3 reproduction; passive trace only."""
import importlib
import json
import os
from pathlib import Path
import sys
import time

from eval.evidence_quality_v2.runtime import isolated_service, write_project, index_project
from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
from docmancer.docs.application.minimal_context_selection import observe_minimal_context
from docmancer.docs.application import source_continuation as binding

audit = importlib.import_module("eval.blind_project_context.step10-multidoc-gate.runner")
ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "eval/blind_project_context/step10-multidoc-gate"
OUT = Path("/tmp/opencode/step10-qwen-capability-repro-01")
MODEL = Path("/tmp/opencode/step10-qwen-reranker-06b-assets")
POLICY = ROOT / "eval/blind_project_context/step10-qwen-calibration/run-01/policy.json"


def main():
    manifest = GATE / "freeze-ready-manifest.json"
    assert audit.digest(manifest.read_bytes()) == "87585ea10a1c0a4e6673020368ad51ee0e64bdd9ca3d6de4ca8ddce86a34046a"
    audit.verify_manifest(manifest)
    assert audit.digest(POLICY.read_bytes()) == "16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11"
    OUT.mkdir(exist_ok=False)
    project = next(p for p in json.loads((GATE / "projects.json").read_text()) if p["id"] == "tidegauge")
    tasks = {t["id"]: t for t in json.loads((GATE / "tasks.json").read_text()) if t["id"] in {"C-T1", "C-T3"}}
    names = project["project_documents"] + [d["path"] for d in project["module_documents"]]
    documents = {n: (GATE / project["root"] / n).read_text() for n in names}
    root = OUT / "project"
    write_project(root, documents)
    import yaml
    catalog_path = root / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    for row in catalog["documents"]:
        if row["path"] == project["module_documents"][0]["path"]:
            row.update(scope="module", module_path=project["module_documents"][0]["module_path"])
    catalog_path.write_text(yaml.safe_dump(catalog))
    counts = {"public_prepares": 0, "public_queries": 0, "resource_reads": 0,
              "model_forwards": 0, "model_input_tokens": 0, "model_totals_complete": True}
    trace, stage = [], "prepare"
    codes = {binding._bind_atomic.__code__, binding.SourceContinuationReader.issue.__code__,
             binding.SourceContinuationReader.issue_range.__code__}

    def tracer(frame, event, arg):
        if frame.f_code not in codes:
            return None
        if event in {"call", "return", "exception"}:
            uri = frame.f_locals.get("uri")
            reader = frame.f_locals.get("self")
            item = {"stage": stage, "function": frame.f_code.co_name, "event": event,
                    "line": frame.f_lineno, "uri": uri,
                    "requested_uri_spent": uri in reader._spent if reader is not None and uri else None,
                    "counts": dict(counts)}
            if event == "return":
                item["return"] = arg if isinstance(arg, (str, type(None))) else type(arg).__name__
            if event == "exception":
                item["exception_type"], item["exception"] = arg[0].__name__, str(arg[1])
            trace.append(item)
        return tracer

    def persist():
        audit.save(OUT / "counts.json", counts)
        audit.save(OUT / "trace.json", trace)

    try:
        with isolated_service(OUT / "state") as (service, config):
            os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="1", DOCATLAS_CONTEXT_COMPRESSION="off",
                              DOCATLAS_MINIMAL_CONTEXT_RECIPE="qwen3-contextual-own-body-evidence-v1",
                              DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH=str(MODEL),
                              DOCATLAS_MINIMAL_CONTEXT_POLICY=str(POLICY))
            counts["public_prepares"] += 1
            persist()
            audit.save(OUT / "prepare.json", index_project(service, config, root))
            with audit.readonly_audit(OUT / "readonly.json", root, config.index.db_path, MODEL):
                for task_id in ("C-T1", "C-T3"):
                    stage = task_id
                    request = {"question": tasks[task_id]["question"], "project_path": str(root), "scope": "project"}
                    packet, observed, error = {}, [], None
                    counts["public_queries"] += 1
                    persist()
                    previous = sys.gettrace()
                    started = time.perf_counter()
                    try:
                        sys.settrace(tracer)
                        with observe_minimal_context() as observed:
                            packet = call_docs_tool_payload("get_docs_context", request, service)
                    except BaseException as exc:
                        error = repr(exc)
                        raise
                    finally:
                        sys.settrace(previous)
                        if len(observed) != 1:
                            counts["model_totals_complete"] = False
                        for item in observed:
                            for key in ("model_forwards", "model_input_tokens"):
                                counts[key] += item["receipt"].get(key, 0)
                        audit.save(OUT / (task_id + ".json"), {"request": request, "packet": packet,
                                   "observations": observed, "error": error, "seconds": time.perf_counter() - started})
                        persist()
                    if task_id == "C-T1":
                        assert packet["status"] == "ok", packet
                        row = next(r for r in packet["sources"] if r["path_or_url"] == "storage.md" and r["line_start"] == 5 and r["line_end"] == 8)
                        uri = row["source_uri"]
                        for label in ("consume", "replay"):
                            stage = label
                            counts["resource_reads"] += 1
                            persist()
                            raw = read_docs_resource(uri, service)
                            audit.save(OUT / (label + ".json"), {"uri": uri, "raw": raw})
                            value = json.loads(raw["text"])
                            if label == "consume":
                                assert value["snippet"] == "".join(documents["storage.md"].splitlines(keepends=True)[value["line_start"]-1:value["line_end"]])
                            else:
                                assert value["reason_code"] == "unknown_or_expired_reference"
                    else:
                        assert packet["reason_code"] == "source_reference_batch_rejected" and not packet["sources"], packet
                        assert any(t["stage"] == "C-T3" and t["function"] == "issue" and t["event"] == "return"
                                   and t["line"] == 99 and t["uri"] == uri and t["requested_uri_spent"] and t["return"] is None for t in trace)
                        assert any(t["stage"] == "C-T3" and t["function"] == "_bind_atomic" and t["event"] == "exception"
                                   and t["exception"] == "source_reference_rejected" for t in trace)
            audit.save(OUT / "summary.json", {"status": "REPRODUCED_SPENT_BRANCH_PUBLIC_REFUSAL", "counts": counts,
                       "manifest_sha256": audit.digest(manifest.read_bytes()), "policy_sha256": audit.digest(POLICY.read_bytes())})
    except BaseException as exc:
        persist()
        audit.save(OUT / "failure.json", {"error": repr(exc), "counts": counts})
        raise


if __name__ == "__main__":
    main()
