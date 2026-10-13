"""One isolated installed-wheel MCP smoke, not a client/production benchmark.

Run with the wheel venv's python -I. All product calls use real SDK stdio.
No transport/storage/retrieval/selection/validation mocks; no live index access.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

# -I intentionally excludes the checkout. Add only the harness directory, which
# contains no docmancer package, so receipt utilities do not defeat wheel isolation.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import database, files, integrity, ledger, save, sha, snapshots

FACT = "Authenticate with OAuth tokens."
DOCUMENTS = {"docs/auth.md": "# Auth\n\n" + FACT + "\n"}
QUESTION = "How do I authenticate with OAuth tokens?"


def decode(result):
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    return json.loads(result.content[0].text)


async def smoke(args):
    manifest = json.loads(args.manifest.read_bytes())
    if not manifest["config"].get("runtime_authorized"):
        raise ValueError("manifest has no runtime authorization")
    for name, digest in manifest["inputs_sha256"].items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError("frozen input changed: " + name)
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import docmancer
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog

    origin = Path(docmancer.__file__).resolve()
    checkout = Path(__file__).resolve().parents[2]
    if origin.is_relative_to(checkout) or not origin.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("must import installed wheel from isolated venv, never checkout")
    if args.work.exists() or args.output.exists():
        raise ValueError("fresh safe work/output required")
    # Reject unsafe host ancestors before provisioning anything. No chmod of user paths.
    parent = args.work.resolve().parent
    for ancestor in (parent, *parent.parents):
        if ancestor.stat().st_mode & 0o022 and not (ancestor.stat().st_mode & 0o1000):
            raise ValueError(f"unsafe storage ancestor: {ancestor}; use explicit secure-home fixture parent")
    args.work.mkdir(mode=0o700)
    args.output.mkdir(parents=True)
    root = args.work.resolve()
    project = root / "project"
    project.mkdir(mode=0o700)
    entries = []
    for name, text in DOCUMENTS.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())
        entries.append(dict(path=name, role="other", scope="project", description="Pinned smoke source",
                            authority="source_of_truth", status="active", impact="track"))
    catalog = project / "docatlas.project-docs.yaml"
    catalog.write_text(json.dumps(dict(schema_version=1, code_files=[], documents=entries)))
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR") if key in os.environ}
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "DOCATLAS_HOME"):
        path = root / key.lower()
        path.mkdir(mode=0o700)
        env[key] = str(path)
    env.update(PYTHONNOUSERSITE="1", DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0",
               DOCATLAS_MCP_ADMIN_TOOLS="0", DOCATLAS_MCP_ADVANCED_TOOLS="0",
               DOCATLAS_REGISTRY_API_URL="http://127.0.0.1:1", NO_PROXY="*")
    if args.arm != "V0":
        env["DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL"] = args.arm
    env["DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS"] = str(manifest["config"]["packing_tokens"])
    storage = Path(env["DOCATLAS_HOME"]) / "mcp-members/members.db"
    mutation = dict(operation="sync_project_docs", confirm=True, storage_path=str(storage),
                    expected_generation_id=None, catalog_sha256=sha(catalog.read_bytes()), documents=[
        dict(path=entry.path, content_sha256=sha((project / entry.path).read_bytes()),
             catalog_entry_hash=catalog_entry_hash(entry)) for entry in read_project_docs_catalog(project).entries])
    receipts = args.output / "EXECUTION_LEDGER.jsonl"
    executable = Path(sys.prefix) / "bin/doc-atlas"
    parameters = StdioServerParameters(command=str(executable), args=["mcp", "docs-serve"], env=env, cwd=str(root))
    counts = dict(prepare=0, context=0, resource=0, model=0)
    async def call(session, tool, arguments):
        counts["prepare" if tool == "prepare_docs" else "context"] += 1
        index = sum(counts.values())
        ledger(receipts, tool, "started", call=index, arguments=arguments)
        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(session.call_tool(tool, arguments), timeout=60)
            payload = decode(result)
            save(args.output / f"call-{index}.json", dict(tool=tool, payload=payload, is_error=result.isError,
                 sdk_result=result.model_dump(mode="json")))
            ledger(receipts, tool, "returned", call=index, seconds=time.perf_counter() - start)
            return payload
        except BaseException as exc:
            ledger(receipts, tool, "error", call=index, error=str(exc))
            raise
    with (args.output / "server.stderr").open("w") as stderr:
        async with stdio_client(parameters, errlog=stderr) as streams:
            async with ClientSession(*streams) as session:
                await asyncio.wait_for(session.initialize(), 60)
                ledger(receipts, "initialize", "returned")
                listed = await asyncio.wait_for(session.list_tools(), 60)
                save(args.output / "tools.json", listed.model_dump(mode="json"))
                ledger(receipts, "list_tools", "returned")
                assert {tool.name for tool in listed.tools} == {"prepare_docs", "get_docs_context", "docs_status"}
                prepared = await call(session, "prepare_docs", dict(action="sync_project_docs", project_path=str(project), mutation=mutation))
                assert prepared.get("status") == "success", prepared
                inventory = dict(storage_path=str(storage), generation_id=prepared["metrics"]["generation_id"])
                save(args.output / "snapshots.json", snapshots(inventory, project, DOCUMENTS))
                before, before_files = database(storage), files(project)
                public = await call(session, "get_docs_context", dict(question=QUESTION, project_path=str(project), scope="project"))
                checks = integrity(public, project, DOCUMENTS)
                save(args.output / "integrity.json", checks)
                assert not checks["errors"], checks
                assert any(FACT in row["snippet"] for row in public.get("sources") or []), public
                row = next(row for row in public["sources"] if row.get("source_uri"))
                counts["resource"] += 1
                ledger(receipts, "read_resource", "started", uri=row["source_uri"])
                resource = await asyncio.wait_for(session.read_resource(row["source_uri"]), 60)
                save(args.output / "resource.json", resource.model_dump(mode="json"))
                ledger(receipts, "read_resource", "returned")
                content = json.loads(resource.contents[0].text)
                if content.get("status") == "complete":
                    assert content.get("reason_code") == "end_of_source"
                else:
                    assert content["content_sha256"] == "sha256:" + sha(DOCUMENTS["docs/auth.md"].encode())
                    assert content["project_identity"] == row["project_identity"]
                    assert Path(content["path"]) == project / "docs/auth.md"
                    start, end = content["line_start"], content["line_end"]
                    assert 1 <= start <= end <= len(DOCUMENTS["docs/auth.md"].splitlines())
                    assert content["snippet"] == "\n".join(DOCUMENTS["docs/auth.md"].splitlines()[start - 1:end])
                version = await call(session, "get_docs_context", dict(question=QUESTION, project_path=str(project), version="99.0.0"))
                assert not version.get("sources") and version.get("answer_available") is not True
                assert database(storage) == before and files(project) == before_files
    save(args.output / "SUMMARY.json", dict(status="completed", boundary="installed wheel stdio MCP, isolated docs-only corpus",
         origin=str(origin), python=sys.executable, arm=args.arm, counts=counts, source_integrity="PASS",
         client_session="NOT RUN", production_smoke="NOT RUN", answer_quality="NOT MEASURED"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", choices=["V0", "Q", "A", "S", "ALL"], default="ALL")
    parser.add_argument("--runtime-authorization", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(asyncio.wait_for(smoke(args), timeout=240))
    except BaseException as exc:
        if args.output.exists():
            save(args.output / "BLOCKED.json", dict(status="BLOCKED", error=str(exc), type=type(exc).__name__))
        raise


if __name__ == "__main__":
    main()
