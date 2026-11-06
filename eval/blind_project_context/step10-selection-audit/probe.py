"""Forensic public-call replay: installed code, frozen inputs, passive scores.

No fitting or changed production components. Run once per named historical input.
This is an installed in-process MCP-handler diagnostic, not stdio/Terra evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--case", choices=("original-v3", "renewed-v1"), required=True)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    base = repo / "eval/blind_project_context"
    config = json.loads((base / "step10-agent-evaluation/renewed-raw/L0/minimal-context/opencode.json").read_text())
    server = config["mcp"]["servers"]["docatlas"]
    for key in list(os.environ):
        if key.startswith("DOCATLAS_") or key == "PYTHONPATH":
            del os.environ[key]
    os.environ.update(server["environment"])
    root = Path(server["cwd"])
    os.chdir(root)
    audit = json.loads((base / "step10-agent-evaluation/renewed-audit.json").read_text())
    if args.case == "original-v3":
        request = {"question": audit["question"]["question"]}
        os.environ["DOCATLAS_MINIMAL_CONTEXT_RECIPE"] = "complete-own-body-gated-maxp-v2"
        os.environ["DOCATLAS_MINIMAL_CONTEXT_POLICY"] = str(base / "step10-calibration-v3/measurement/policy.json")
    else:
        request = audit["mcp_input"]
        os.environ["DOCATLAS_MINIMAL_CONTEXT_RECIPE"] = "complete-maxp-token-overlap-v1"

    import docmancer
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    from docmancer.docs.application.minimal_context_selection import observe_minimal_context

    module = Path(docmancer.__file__).resolve()
    assert "site-packages" in module.parts, module
    code_paths = sorted(module.parent.rglob("*.py"))
    equality = {str(p.relative_to(module.parent)): digest(p.read_bytes()) == digest(
        (repo / "docmancer" / p.relative_to(module.parent)).read_bytes()) for p in code_paths}
    assert all(equality.values()), [k for k, v in equality.items() if not v]

    def state():
        files = {str(p.relative_to(root)): digest(p.read_bytes())
                 for p in sorted((root / "project").rglob("*")) if p.is_file()}
        databases = {}
        for p in sorted((root / "docatlas-home").rglob("*.db")):
            with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True) as db:
                databases[str(p.relative_to(root))] = digest("\n".join(db.iterdump()).encode())
        return {"files": files, "logical_databases": databases}

    def save(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    before = state()
    save("input.json", {"request": request, "case": args.case, "state": before,
                        "policy": json.loads(Path(os.environ["DOCATLAS_MINIMAL_CONTEXT_POLICY"]).read_text())})
    service = create_local_mcp_service()
    started = time.perf_counter()
    with observe_minimal_context() as observations:
        packet = call_docs_tool_payload("get_docs_context", request, service)
    elapsed = time.perf_counter() - started
    save("packet.json", packet)
    save("observations.json", observations)
    after = state()
    save("execution.json", {"seconds": elapsed, "public_calls": 1,
                            "sources_and_logical_database_unchanged": before == after})
    assert before == after, "Public read changed source/database state"
    assert len(observations) == 1
    scores = observations[0]["scores"]
    for row in scores:
        raw = (root / "project" / row["path"]).read_bytes()
        assert digest(raw) == row["source_sha256"]
    rows = packet.get("sources", [])
    for row in rows:
        raw = (root / "project" / row["path_or_url"]).read_bytes().decode()
        expected = "".join(raw.splitlines(keepends=True)[row["line_start"] - 1:row["line_end"]])
        assert row["snippet"] == expected
        lineage = next(json.loads(s["source_identity"])["candidate"] for s in scores
                       if s["path"] == row["path_or_url"])
        assert row["scope"] == lineage["doc_scope"]
        assert row["authority"] == lineage["authority"]
    facts = ["Branch name: `feat/<topic>` or `fix/<description>`",
             "Run the full test suite before opening the PR",
             "New connectors or fetchers should include tests where practical"]
    assert all(f in (root / "project/CONTRIBUTING.md").read_text() for f in facts)
    ordered = sorted(scores, key=lambda r: r["score"], reverse=True)
    brief = [{"rank": i + 1, **{k: row[k] for k in (
        "path", "heading_path", "line_start", "line_end", "score", "contextual_score",
        "own_body_score", "pairs", "body_tokens", "ancestor_tokens") if k in row}}
        for i, row in enumerate(ordered)]
    save("ranked-scores.json", brief)
    receipt = {"boundary": "installed_in_process_public_MCP_handler_with_passive_observer",
               "case": args.case, "request": request, "python": sys.executable,
               "module": str(module), "code_files_equal": len(equality),
               "seconds": elapsed, "public_calls": 1, "terra_calls": 0,
               "sources_and_logical_database_unchanged": before == after,
               "exact_source_spans_checked": len(rows),
               "facts": [any(f in r["snippet"] for r in rows) for f in facts],
               "selection": packet.get("source_selection"),
               "scoring": observations[0]["receipt"],
               "contributing": [r for r in brief if r["path"] == "CONTRIBUTING.md"]}
    save("receipt.json", receipt)
    save("sha256.json", {p.name: digest(p.read_bytes()) for p in sorted(out.glob("*.json"))})
    print(json.dumps({k: v for k, v in receipt.items() if k != "scoring"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
