"""Public fresh-capability regression; frozen semantic policy, no fitting."""
import importlib
import json
import os
from pathlib import Path
import time

from eval.evidence_quality_v2.runtime import isolated_service, write_project, index_project
from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
from docmancer.docs.application.minimal_context_selection import observe_minimal_context
from docmancer.docs.application.standalone_text_view import render_standalone_text
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.domain.minimal_context_config import EMERGENCY_TOKENS

audit = importlib.import_module("eval.blind_project_context.step10-multidoc-gate.runner")
prior = importlib.import_module("eval.blind_project_context.step10-qwen-capability-repro.reproduce")
OUT = Path("/tmp/opencode/step10-qwen-capability-repair-01")


def main():
    OUT.mkdir(exist_ok=False)
    tasks = {t["id"]: t for t in json.loads((prior.GATE / "tasks.json").read_text())}
    project = next(p for p in json.loads((prior.GATE / "projects.json").read_text()) if p["id"] == "tidegauge")
    documents = {n: (prior.GATE / project["root"] / n).read_text() for n in
                 project["project_documents"] + [d["path"] for d in project["module_documents"]]}
    labels = {t["task_id"]: t["units"] for t in json.loads((prior.GATE / "draft-labels.json").read_text())}
    root = OUT / "project"
    write_project(root, documents)
    import yaml
    path = root / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(path.read_text())
    for row in catalog["documents"]:
        if row["path"] == project["module_documents"][0]["path"]:
            row.update(scope="module", module_path=project["module_documents"][0]["module_path"])
    path.write_text(yaml.safe_dump(catalog))
    counts = {"public_prepares": 0, "public_queries": 0, "resource_reads": 0,
              "model_forwards": 0, "model_input_tokens": 0, "model_totals_complete": True}

    def persist():
        audit.save(OUT / "counts.json", counts)

    try:
        assert audit.digest(prior.POLICY.read_bytes()) == "16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11"
        with isolated_service(OUT / "state") as (service, config):
            os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="1", DOCATLAS_CONTEXT_COMPRESSION="off",
                              DOCATLAS_MINIMAL_CONTEXT_RECIPE="qwen3-contextual-own-body-evidence-v1",
                              DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH=str(prior.MODEL),
                              DOCATLAS_MINIMAL_CONTEXT_POLICY=str(prior.POLICY))
            counts["public_prepares"] += 1
            persist()
            audit.save(OUT / "prepare.json", index_project(service, config, root))
            with audit.readonly_audit(OUT / "readonly.json", root, config.index.db_path, prior.MODEL):
                def query(task_id, name):
                    request = {"question": tasks[task_id]["question"], "project_path": str(root), "scope": "project"}
                    counts["public_queries"] += 1
                    persist()
                    packet, observed, error = {}, [], None
                    start = time.perf_counter()
                    try:
                        with observe_minimal_context() as observed:
                            packet = call_docs_tool_payload("get_docs_context", request, service)
                    except BaseException as exc:
                        error = repr(exc)
                        raise
                    finally:
                        if len(observed) != 1:
                            counts["model_totals_complete"] = False
                        for o in observed:
                            for key in ("model_forwards", "model_input_tokens"):
                                counts[key] += o["receipt"].get(key, 0)
                        audit.save(OUT / (name + ".json"), {"request": request, "packet": packet,
                                   "observations": observed, "error": error, "seconds": time.perf_counter() - start})
                        persist()
                    checked, _ = audit.packet_check(packet, observed[0], tasks[task_id], project, labels[task_id],
                                                    projection_token_count, "local:" + audit.digest(str(root).encode()))
                    assert not checked["missing_required_units"] and not checked["missing_facts"] and not checked["hard_negatives"], checked
                    rendered = render_standalone_text(packet)
                    text = rendered.text if rendered.text is not None else json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
                    measured = projection_token_count(text.encode())
                    assert measured <= EMERGENCY_TOKENS
                    audit.save(OUT / (name + "-checks.json"), {**checked, "actual_rendered_tokens": measured,
                               "emergency_tokens": EMERGENCY_TOKENS})
                    return packet

                def read(uri, name, unavailable=False):
                    counts["resource_reads"] += 1
                    persist()
                    result, error = None, None
                    start = time.perf_counter()
                    try:
                        result = read_docs_resource(uri, service)
                    except BaseException as exc:
                        error = repr(exc)
                        raise
                    finally:
                        audit.save(OUT / (name + ".json"), {"uri": uri, "raw": result, "error": error,
                                   "seconds": time.perf_counter() - start})
                    value = json.loads(result["text"])
                    if unavailable:
                        assert value["reason_code"] == "unknown_or_expired_reference" and "snippet" not in value
                    else:
                        assert value["path"] == "storage.md" and value["line_start"] == 9 and value["line_end"] == 12
                        assert value["snippet"] == "".join(documents["storage.md"].splitlines(keepends=True)[8:12])
                        assert value["content_sha256"] == "sha256:" + audit.digest(documents["storage.md"].encode())
                        assert value["project_identity"] == "local:" + audit.digest(str(root).encode())

                def retention(packet):
                    return next(r["source_uri"] for r in packet["sources"] if r["path_or_url"] == "storage.md"
                                and r["line_start"] == 5 and r["line_end"] == 8)

                first = query("C-T1", "C-T1")
                old = retention(first)
                read(old, "consume-U")
                read(old, "replay-U", True)
                fresh = query("C-T3", "C-T3-fresh")
                new = retention(fresh)
                assert new != old
                reused = query("C-T3", "C-T3-reuse")
                assert reused == fresh and retention(reused) == new
                read(new, "consume-V")
                read(old, "old-U-remains-spent", True)
                read(new, "replay-V", True)
            audit.save(OUT / "summary.json", {"status": "PASS_PUBLIC_LIFECYCLE_REGRESSION", "counts": counts,
                       "old_uri": old, "new_uri": new, "exact_active_alias_packet_reuse": True,
                       "boundary": "not calibration acceptance; new root and generation"})
    except BaseException as exc:
        persist()
        audit.save(OUT / "failure.json", {"error": repr(exc), "counts": counts})
        raise


if __name__ == "__main__":
    main()
