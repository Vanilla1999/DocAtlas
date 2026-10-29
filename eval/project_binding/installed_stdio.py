"""Real installed stdio regression for missing project/library binding.

The original B01 B02 B05 B06 B08 questions are immutable. This is a public
MCP/SQLite/MiniLM acceptance, not an autonomous paid OpenCode session.
"""
import argparse
import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

CASES = (
    ("B01", "What is Black's default line length?"),
    ("B02", "How does Black determine target Python versions when --target-version is not set?"),
    ("B05", "How does --force-exclude differ from --exclude for files passed explicitly to Black?"),
    ("B06", "Where does Black search for pyproject.toml, and what TCP port does blackd listen on by default?"),
    ("B08", "What guaranteed 99th-percentile formatting latency in milliseconds does Black provide?"),
)

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def source_docs(repo):
    base = repo / "eval/prepared_model_comparison40/sources/black"
    found = {p.relative_to(base).as_posix(): p.read_text(encoding="utf-8")
             for p in base.rglob("*.md") if p.is_file()}
    expected = json.loads((repo / "eval/context_assembly/questions20.json").read_text())["source_sha256"]
    assert len(found) == 3, found.keys()
    for path, content in found.items():
        assert hashlib.sha256(content.encode()).hexdigest() == expected["black/" + path]
    return found

def worker(a):
    from docmancer.mcp._docs_server_part01 import _run_async
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime = load("binding_runtime", a.repo / "eval/evidence_quality_v2/runtime.py")
    state = load("binding_state", a.repo / "eval/prepared_model_comparison40/run.py")
    root = a.work / "black"
    runtime.write_project(root, source_docs(a.repo))
    with runtime.isolated_service(a.work / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        save(a.out / "PREPARE.json", inventory)
        before = state.logical_state(inventory), state.source_state(root)
        os.environ.update(DOCATLAS_MINILM_MODEL_DIR="/model", DOCATLAS_MCP_TEXT_FALLBACK="1",
                          DOCATLAS_MCP_COMPACT_TEXT="1", DOCATLAS_MCP_MODEL_VIEW="off",
                          HF_HUB_OFFLINE="1", DOCATLAS_OFFLINE="1")
        with observe_section_compression() as observations:
            try:
                asyncio.run(_run_async(service))
            finally:
                save(a.out / "SERVER.json", {
                    "observations": observations,
                    "database_unchanged": before[0] == state.logical_state(inventory),
                    "files_unchanged": before[1] == state.source_state(root),
                })

def contents(result):
    assert len(result.content) == 1 and result.content[0].type == "text"
    assert result.structuredContent is None and not getattr(result, "_meta", None)
    return json.loads(result.content[0].text), result.content[0].text

def checked_rows(result, docs):
    from docmancer.docs.application.context_assembly import decode_context
    from docmancer.docs.application.section_compression import expand_sections
    fmt = str(result.get("context_format") or "")
    if fmt.startswith("docatlas.assembled-") or fmt == "docatlas.standalone-text.v1":
        p = decode_context(result)
        inherited = p.get("source_context") or {}
        rows = [{**inherited, **row} for row in p["sources"]]
    else:
        raw = expand_sections(result)
        rows = [{"path": r["path_or_url"], "text": r["snippet"],
                 "ref": r["evidence_id"], "source_uri": r.get("source_uri"),
                 "line_start": r.get("line_start"), "line_end": r.get("line_end"),
                 "scope": r.get("scope")} for r in raw.get("sources", [])]
    for row in rows:
        path, text = row["path"], row["text"]
        assert path in docs and isinstance(text, str) and text
        start, end = row["line_start"], row["line_end"]
        lines = docs[path].splitlines(keepends=True)
        assert type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)
        assert text in "".join(lines[start - 1:end])
        assert row["scope"] == "project"
        assert isinstance(row["ref"], str) and row["ref"]
        assert row.get("source_uri", "").startswith("docatlas://source/")
    return rows, fmt

async def run(a):
    import jsonschema
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    root = a.work / "black"
    originals = source_docs(a.repo)
    params = StdioServerParameters(command=sys.executable,
        args=["-I", str(Path(__file__).resolve()), "--worker",
              "--repo", str(a.repo), "--work", str(a.work), "--out", str(a.out)],
        env=dict(os.environ))
    rows = []
    with (a.out / "MCP_STDERR.log").open("w") as stderr:
        async with stdio_client(params, errlog=stderr) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=240)) as session:
                await session.initialize()
                spec = next(t for t in (await session.list_tools()).tools if t.name == "get_docs_context")
                schema = spec.inputSchema
                assert "KNOWN ABSOLUTE" in spec.description and "anyOf" in schema
                validator = jsonschema.Draft202012Validator(schema)
                for _, q in CASES:
                    assert not validator.is_valid({"question": q})
                    assert not validator.is_valid({"question": q, "project_path": None, "library": None})
                    assert not validator.is_valid({"question": q, "project_path": ""})
                    assert validator.is_valid({"question": q, "project_path": str(root)})
                    assert validator.is_valid({"question": q, "library": "black"})
                print(json.dumps({"real_advertised_schema": "requires_explicit_target"}), flush=True)
                for case_id, question in CASES:
                    started = time.monotonic()
                    unbound = await session.call_tool("get_docs_context", {"question": question})
                    denied, text = contents(unbound)
                    assert unbound.isError is True, (case_id, denied)
                    assert denied["status"] == "failed" and not denied.get("sources")
                    error = denied["error"]
                    assert error["reason_code"] == "docs_context_target_missing", (case_id, denied)
                    assert error["where"]["phase"] == "validation" and error["retryable"] is False
                    assert "project_path" in error["message"] and "library" in error["message"]
                    assert any("absolute" in h.lower() and "project_path" in h for h in error["hints"])
                    assert "No safe bounded selected context is available." not in text
                    bound_start = time.monotonic()
                    found = await session.call_tool("get_docs_context", {
                        "question": question, "project_path": str(root)
                    })
                    answer, raw = contents(found)
                    assert not found.isError and answer.get("kind") == "docs_context", (case_id, answer)
                    assert answer.get("status") in {"ok", "truncated"}, (case_id, answer)
                    refs, fmt = checked_rows(answer, originals)
                    assert refs, (case_id, "no selected source evidence after binding")
                    item = {"id": case_id, "question": question,
                            "unbound": {"status": denied["status"], "reason_code": error["reason_code"],
                                        "isError": unbound.isError, "sources": 0},
                            "bound": {"status": answer["status"], "source_rows": len(refs),
                                      "context_format": fmt, "tool_isError": bool(found.isError),
                                      "text_o200k": projection_token_count(raw.encode())},
                            "time": {"unbound_s": bound_start-started,
                                     "bound_s": time.monotonic()-bound_start}}
                    rows.append(item)
                    print(json.dumps(item), flush=True)
                # Library-only queries are a valid target choice; they must
                # not be rejected as if project_path were globally required.
                lib = await session.call_tool("get_docs_context", {
                    "question": CASES[0][1], "library": "black"
                })
                packet, _ = contents(lib)
                assert (packet.get("error") or {}).get("reason_code") != "docs_context_target_missing"
                assert packet.get("reason_code") != "docs_context_target_missing"
                # No automatic fallback to server CWD / a different project.
                missing = await session.call_tool("get_docs_context", {
                    "question": CASES[0][1], "project_path": str(a.work / "nonexistent")
                })
                missing_packet, _ = contents(missing)
                assert missing_packet["status"] not in {"ok", "truncated"}
                assert not missing_packet.get("sources")

    state = json.loads((a.out / "SERVER.json").read_text())
    assert state["database_unchanged"] and state["files_unchanged"]
    assert len(rows) == 5
    outcome = {"pass": True, "questions": [r["id"] for r in rows],
               "typed_unbound_errors": 5, "target_bound_with_evidence": 5,
               "real_installed_MCP": True, "real_SQLite_prepare": True,
               "real_MiniLM_selection": True, "source_spans_verified": True,
               "unbound_is_not_semantic_insufficiency": True,
               "library_only_allowed": True, "unavailable_path_does_not_fall_back": True,
               "files_and_sqlite_unchanged": True,
               "autonomous_opencode_tool_calls": "NOT_TESTED",
               "paid_model_usage": None, "results": rows}
    save(a.out / "RESULT.json", outcome)
    print(json.dumps({k:v for k,v in outcome.items() if k != "results"}), flush=True)

def main():
    p = argparse.ArgumentParser()
    for field in ("repo", "work", "out"):
        p.add_argument("--"+field, required=True, type=Path)
    p.add_argument("--worker", action="store_true")
    a = p.parse_args()
    for field in ("repo","work","out"):
        setattr(a, field, getattr(a,field).resolve())
    if a.worker:
        worker(a)
    else:
        import docmancer
        installed = Path(docmancer.__file__).resolve().parent
        assert not installed.is_relative_to(a.repo)
        for p in ("mcp/_docs_server_tool_data.py", "mcp/_docs_server_part01.py",
                  "docs/interfaces/mcp/context_tools.py", "docs/interfaces/mcp/error_contract.py"):
            assert (installed / p).read_bytes() == (a.repo / "docmancer" / p).read_bytes()
        a.out.mkdir(parents=True, exist_ok=True)
        a.work.mkdir(parents=True, exist_ok=True)
        asyncio.run(run(a))

if __name__ == "__main__":
    main()
