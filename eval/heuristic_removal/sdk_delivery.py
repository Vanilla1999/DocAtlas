"""Model-free public SDK delivery audit on pinned documents and real SQLite."""
from __future__ import annotations

import json
from pathlib import Path

from docmancer import DocmancerClient
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2 import runtime
from eval.heuristic_removal.receipts import database, files
from tests.test_prepared_retrieval_integration import CHECKLIST_DOCUMENTS


def observe(work: Path, audit: Path) -> dict:
    original = json.loads((audit / "SDK_BUDGET_REPRO.json").read_text())
    root = work / "project"
    documents = {**original["documents"], **CHECKLIST_DOCUMENTS}
    runtime.write_project(root, documents)
    with runtime.isolated_service(work / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        sdk = DocmancerClient(db_path=inventory["storage_path"])
        before = database(inventory["storage_path"]), files(root)
        small = sdk.get_chunks("Observatory", limit=1, budget=100)
        tight = sdk.get_context("Observatory", limit=1, budget=100)
        wide = sdk.get_chunks("Observatory", limit=20, budget=12000)
        wide_text = sdk.get_context("Observatory", limit=20, budget=12000)
        # Independent fact: the following line belongs to the same checklist,
        # but does not match "Photograph". Do not infer it from chunker output.
        expected_neighbor = "Complete every dispatch checklist step before handing over an optical case."
        agent = sdk._agent
        bare = sdk.get_chunks("Photograph", limit=20, budget=12000, expand="none")
        adjacent = sdk.get_chunks("Photograph", limit=20, budget=12000, expand="adjacent")
        page = sdk.get_chunks("Photograph", limit=20, budget=12000, expand="page")
        expanded_text = sdk.get_context("Photograph", limit=20, budget=600, expand="adjacent")
        zero_chunks = sdk.get_chunks("Observatory", limit=0, budget=0)
        zero_text = sdk.get_context("Observatory", limit=0, budget=0)
        dispatcher = RetrievalDispatcher(store=agent.store, config=config)
        acquired = dispatcher.run("Observatory", mode="lexical", limit=1, budget=100).chunks
        expanded = dispatcher.run("Photograph", mode="lexical", expand="adjacent").chunks
        def rows(chunks):
            return [dict(source=c.source, text=c.text, metadata=c.metadata) for c in chunks]
        return {
            "boundary": "public SDK/Agent/Dispatcher, prepared SQLite, no mocks/models",
            "requested_limit": 1, "requested_budget": 100,
            "small": rows(small), "tight_text": tight,
            "wide": rows(wide), "wide_text": wide_text,
            "bare": rows(bare), "adjacent": rows(adjacent), "page": rows(page),
            "expanded_text": expanded_text, "zero_chunks": rows(zero_chunks), "zero_text": zero_text,
            "dispatcher_acquired": rows(acquired), "dispatcher_expanded": rows(expanded),
            "expected_neighbor": expected_neighbor,
            "documents": documents,
            "state_unchanged": before == (database(inventory["storage_path"]), files(root)),
        }


def main():
    """Prepare via source public MCP, then verify installed SDK without checkout imports."""
    import argparse
    import subprocess
    from tempfile import TemporaryDirectory
    from eval.heuristic_removal.receipts import save
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    audit = repo / "reports/docatlas-grounded-20261013/pre-model-research-audit"
    docs = {**json.loads((audit / "SDK_BUDGET_REPRO.json").read_text())["documents"],
            **CHECKLIST_DOCUMENTS}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory(dir="/tmp/opencode", prefix="sdk-installed-fixture-") as work:
        project = Path(work) / "project"
        runtime.write_project(project, docs)
        with runtime.isolated_service(Path(work) / "state") as (service, config):
            inv = runtime.index_project(service, config, project)
            manifest = output / "fixture.json"
            save(manifest, dict(project=str(project), storage_path=inv["storage_path"],
                                generation_id=inv["generation_id"], documents=docs))
            proc = subprocess.run([
                str(args.installed_python.absolute()), "-I",
                str(repo / "eval/heuristic_removal/installed_sdk_delivery.py"),
                "--fixture", str(manifest), "--output", str(output / "RESULT.json"),
            ], cwd=work, capture_output=True, text=True, timeout=90)
            (output / "stdout.log").write_text(proc.stdout)
            (output / "stderr.log").write_text(proc.stderr)
            if proc.returncode:
                raise RuntimeError(f"installed SDK failed: {proc.stderr}")


if __name__ == "__main__":
    main()
