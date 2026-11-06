"""Authorized public Qwen preflight on existing structural fixture, never gate data."""
import argparse
from contextlib import nullcontext
import importlib
import json
import os
from pathlib import Path
import sys
import time

from eval.blind_project_context.probe_minimal_structure import DOCUMENTS, QUESTION
from eval.evidence_quality_v2.runtime import isolated_service, write_project, index_project
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.application import context_evidence_scoring as scorer
from docmancer.docs.application.minimal_context_selection import observe_minimal_context

audit = importlib.import_module("eval.blind_project_context.step10-multidoc-gate.runner")


def main(args):
    if not __debug__:
        raise ValueError("assertions required")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    counts = {"public_prepares": 0, "public_queries": 0, "resource_reads": 0,
              "model_forwards": 0, "model_input_tokens": 0, "model_totals_complete": True}
    results = {}

    def persist():
        audit.save(out / "counts.json", counts)

    try:
        for scenario in ([args.scenario] if args.scenario != "all" else ["parity", "overflow"]):
            dest = out / scenario
            project = dest / "project"
            documents = dict(DOCUMENTS)
            if scenario == "overflow":
                documents["docs/other.md"] += "\n## Extended procedure\n\n" + "Record the measured pressure before continuing. " * 5000 + "\n"
            write_project(project, documents)
            audit.save(dest / "request.json", {"question": QUESTION, "project_path": str(project),
                       "scope": "project", "scenario": scenario, "policy": None})
            with isolated_service(dest / "state") as (service, config):
                os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="1", DOCATLAS_CONTEXT_COMPRESSION="off",
                                  DOCATLAS_MINIMAL_CONTEXT_RECIPE=scorer.RECIPE,
                                  DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH=str(args.model.resolve()))
                os.environ.pop("DOCATLAS_MINIMAL_CONTEXT_POLICY", None)
                counts["public_prepares"] += 1
                persist()
                try:
                    prepared = index_project(service, config, project)
                    audit.save(dest / "prepare.json", prepared)
                except BaseException as exc:
                    audit.save(dest / "prepare-failure.json", {"error": repr(exc), "sources": audit.source_hashes(project)})
                    raise
                with audit.readonly_audit(dest / "readonly.json", project, config.index.db_path, args.model.resolve()):
                    for mode in (["off", "on"] if scenario == "parity" else ["overflow"]):
                        passive = []

                        def profile(frame, event, value):
                            if event == "return" and frame.f_code is scorer.score_evidence_units.__code__:
                                # Retain scalar work receipt only, never OFF scores/prompts.
                                passive.append(dict(frame.f_locals["receipt"]))

                        packet, observations, error = {}, [], None
                        counts["public_queries"] += 1
                        persist()
                        started = time.perf_counter()
                        previous = sys.getprofile()
                        try:
                            if mode == "off":
                                sys.setprofile(profile)
                            with observe_minimal_context() if mode != "off" else nullcontext([]) as observations:
                                packet = call_docs_tool_payload("get_docs_context", {
                                    "question": QUESTION, "project_path": str(project), "scope": "project"}, service)
                        except BaseException as exc:
                            error = repr(exc)
                            raise
                        finally:
                            sys.setprofile(previous)
                            receipts = passive if mode == "off" else [o["receipt"] for o in observations]
                            if not receipts and packet.get("source_selection", {}).get("receipt"):
                                receipts = [packet["source_selection"]["receipt"]]
                            if len(receipts) != 1:
                                counts["model_totals_complete"] = False
                            for receipt in receipts:
                                for key in ("model_forwards", "model_input_tokens"):
                                    counts[key] += receipt.get(key, 0)
                            result = {"packet": packet, "observations": observations, "work_receipts": receipts,
                                      "error": error, "seconds": time.perf_counter() - started,
                                      "trace_status": "available" if len(receipts) == 1 else "lost_trace_unknown_work"}
                            audit.save(dest / (mode + ".json"), result)
                            results[mode] = result
                            persist()
                        if scenario == "overflow":
                            assert packet.get("reason_code") == "scan_incomplete", packet
                            assert len(receipts) == 1 and receipts[0]["model_forwards"] == 0, result
                            assert "evidence_prompt_overflow:" in receipts[0].get("error", ""), result
                            assert not packet.get("sources"), packet
                        else:
                            assert packet["source_selection"]["scan_complete"], packet
                            assert len(receipts) == 1 and receipts[0]["status"] == "complete"
                            assert len(observations) == int(mode == "on")
                            for row in packet["sources"]:
                                raw = documents[row["path_or_url"]]
                                exact = "".join(raw.splitlines(keepends=True)[row["line_start"] - 1:row["line_end"]])
                                assert exact == row["snippet"] and row["scope"] == "project"
                                assert row["authority"] == "source_of_truth" and row["version_binding"] == "unversioned"
                                assert row["project_identity"] == "local:" + audit.digest(str(project).encode())
                                material = {"path": row["path_or_url"], "section": row.get("section"),
                                            "content": exact, "snippet": exact, "version": None}
                                assert audit.digest(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                                    separators=(",", ":")).encode()) == row["content_sha256"]
                            delivered = "".join(row["snippet"] for row in packet["sources"])
                            for exact in ("## Empty", "Tail condition stays.", "[^note]: Footnote condition.\n    Continued footnote.",
                                          "[ref]:\n  other.md#remote", "Remote condition", "Scope introduction."):
                                assert exact in delivered, exact
                            assert any(g["target"] == "private.md#hidden" for g in packet["source_selection"]["closure"]["incomplete_dependencies"])
                    if scenario == "parity":
                        assert results["off"]["packet"] == results["on"]["packet"], "exact public packet parity"
                        off, on = (results[k]["work_receipts"][0] for k in ("off", "on"))
                        for key in ("model_forwards", "model_input_tokens", "model_pairs", "units"):
                            assert off[key] == on[key], key
                        assert off["diagnostics_recorded"] == 0 and off["diagnostics_omitted"] == off["units"]
                        assert on["diagnostics_recorded"] == on["units"]
        audit.save(out / "summary.json", {"status": "PASS_PUBLIC_DIAGNOSTIC_ONLY", "counts": counts,
                   "semantic_sufficiency": "not tested", "32k_forward": "not tested",
                   "gate_queries": 0, "boundary": "public in-process prepare/get_docs_context"})
    except BaseException as exc:
        audit.save(out / "failure.json", {"status": "FAIL_NOT_PASS", "error": repr(exc), "counts": counts})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scenario", choices=("all", "parity", "overflow"), default="all")
    main(parser.parse_args())
