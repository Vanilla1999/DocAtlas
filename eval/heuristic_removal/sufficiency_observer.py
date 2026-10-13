"""Installed public observer isolation; scripted assessor, not model accuracy."""
from contextlib import nullcontext
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import database, files, integrity, save, sha, snapshots, stable_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.work.exists() or args.output.exists():
        raise ValueError("fresh work/output required")
    args.work.mkdir(parents=True, mode=0o700)
    for key in tuple(os.environ):
        if key.startswith("DOCATLAS_EXPERIMENT_"):
            del os.environ[key]
    os.environ["DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS"] = "12000"
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("fixture", repo / "eval/evidence_quality_v2/runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    import docmancer
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application.context_sufficiency import context_sufficiency_observer
    origin = Path(docmancer.__file__).resolve()
    assert not origin.is_relative_to(repo) and origin.is_relative_to(Path(sys.prefix).resolve())
    documents = {"docs/control.md": "# Observatory aperture control\n\n"
                 "aperture_control sets the lens aperture. The required value is f/8.\n"}
    question = "What does aperture_control set and which value is required?"
    root = (args.work / "project").resolve()
    runtime.write_project(root, documents)
    assessed_inputs = []

    def checker(*, question, final_context_json):
        assessed_inputs.append((question, final_context_json))
        copy = json.loads(final_context_json)
        ids = [row["evidence_id"] for row in copy["sources"]]
        copy["sources"].clear()
        return dict(status="sufficient", supported_obligations=["scripted external assessor response"],
                    missing_obligations=[], evidence_ids=ids)

    def failure(**kwargs):
        raise RuntimeError("scripted external assessor failure")

    def invented(**kwargs):
        return dict(status="sufficient", supported_obligations=["scripted invalid citation"],
                    missing_obligations=[], evidence_ids=["not-present-in-final-packet"])

    result = dict(boundary="installed public in-process MCP; not stdio/client/production",
                  installed_origin=str(origin), preparations=0, contexts=0, model_calls=0,
                  assessor_boundary="scripted external assessor; semantic accuracy NOT MEASURED", records=[])
    with runtime.isolated_service(args.work / "state") as (service, config):
        result["preparations"] += 1
        inventory = runtime.index_project(service, config, root)
        snapshots(inventory, root, documents)
        before_db, before_files = database(inventory["storage_path"]), files(root)
        packets = []
        for label, assessor in (("off", None), ("on", checker), ("error", failure), ("invalid_citation", invented)):
            scope = context_sufficiency_observer(assessor) if assessor else nullcontext()
            with scope as observation:
                result["contexts"] += 1
                payload = call_docs_tool_payload("get_docs_context", dict(
                    question=question, project_path=str(root), scope="project"), service)
            checks = integrity(payload, root, documents)
            assert not checks["errors"]
            assert any("aperture_control sets the lens aperture. The required value is f/8." in row["snippet"]
                       for row in payload["sources"])
            assert payload["answer_supported"] is False and payload["edit_ready"] is False
            assert database(inventory["storage_path"]) == before_db and files(root) == before_files
            receipt = observation.records[0] if observation else None
            if receipt:
                assert observation.calls == 1
                assert receipt["final_context_sha256"] == sha(json.dumps(payload, ensure_ascii=False).encode())
            result["records"].append(dict(label=label, payload=payload, diagnostic=receipt, integrity=checks))
            packets.append(payload)
        assert all(stable_packet(packet) == stable_packet(packets[0]) for packet in packets[1:])
        assert assessed_inputs == [(question, json.dumps(packets[1], ensure_ascii=False))]
        assert result["records"][1]["diagnostic"]["status"] == "sufficient"
        for record in result["records"][2:]:
            assert record["diagnostic"]["status"] == "unknown" and record["diagnostic"]["observation"] == "error"
        result.update(status="PASS", read_only=True, delivery_equivalent=True,
                      unsupported_authority=False, model_accuracy="NOT MEASURED")
    save(args.output, result)
    print("PASS: installed observer isolation,4 public contexts,0 model calls")


if __name__ == "__main__":
    main()
