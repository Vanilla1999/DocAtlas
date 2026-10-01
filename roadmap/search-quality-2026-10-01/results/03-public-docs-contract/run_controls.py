"""Documentation consistency controls, not a recall-success benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import docmancer
from docmancer.core.config import DocmancerConfig
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload, current_tools


def run(args):
    repo = Path(args.repo).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = Path(tempfile.mkdtemp(prefix="docs-contract-controls-", dir="/tmp/opencode"))
    paths = ["wiki/Architecture.md", "wiki/Troubleshooting.md", "wiki/Configuration.md",
             "docs/mcp-docs-server.md", "docs/source-continuation.md", "docs/AGENT_DOCS_WORKFLOW.md", "SKILL.md"]
    blocks = []
    hashes = {}
    for path in paths:
        source = repo / path
        target = fixture / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[path] = hashlib.sha256(target.read_bytes()).hexdigest()
        blocks.append(f"  - path: {path}\n    role: runbook\n    scope: project\n    authority: source_of_truth\n    status: active\n    description: Current public contract for {path}\n")
    (fixture / "docatlas.project-docs.yaml").write_text("schema_version: 1\ndocuments:\n" + "".join(blocks))
    (fixture / "pyproject.toml").write_text('[project]\nname="docs-contract-controls"\nversion="0.1"\n')
    config = DocmancerConfig()
    config.index.db_path = str(fixture / "state/index.db")
    config.index.extracted_dir = str(fixture / "state/extracted")
    service = LibraryDocsService(config=config, config_source="explicit")
    assert service.sync_project_docs(str(fixture), with_vectors=False).status == "success"
    review = (repo / "roadmap/search-quality-2026-10-01/audit/PROJECT_80_REVIEW_RU.md").read_text()
    questions = {}
    for line in review.splitlines():
        if not line.startswith("| project"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        identity = cells[1]
        if identity.split("-")[-1] in {"Q11", "Q12", "Q14", "Q25", "Q26"}:
            questions[identity] = cells[2]
    assert len(questions) == 10
    for identity, question in questions.items():
        payload = call_docs_tool_payload("get_docs_context", {
            "question": question, "project_path": str(fixture), "scope": "all",
        }, service)
        assert payload.get("answer_supported", False) is False
        assert payload.get("edit_ready", False) is False
        for source in payload.get("sources", []):
            assert source["snippet"] in (fixture / source["path_or_url"]).read_text(), source
        (out / f"{identity}.json").write_text(json.dumps({"question": question, "payload": payload}, ensure_ascii=False, indent=2) + "\n")
    (out / "provenance.json").write_text(json.dumps({
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "runtime_import": docmancer.__file__, "fixture": str(fixture), "corpus_sha256": hashes,
        "tools": current_tools(), "question_count": len(questions),
        "purpose": "Packet inspection for text consistency; not answer generation, recall comparison or independent gate",
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {len(questions)} control packets to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
