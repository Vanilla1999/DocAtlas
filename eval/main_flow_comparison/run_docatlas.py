"""One real stdio MCP preparation followed by the ten frozen questions."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(__file__).resolve().parent


def decode(response):
    if isinstance(response.structuredContent, dict):
        return response.structuredContent
    return json.loads("\n".join(item.text for item in response.content if item.type == "text"))


async def main():
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog
    import docmancer

    assert Path(docmancer.__file__).resolve().is_relative_to(ROOT)
    isolated = Path.home() / ".docatlas-main-flow-comparison-20261011"
    isolated.mkdir(mode=0o700, exist_ok=False)
    project = isolated / "project"
    project.mkdir(mode=0o700)
    corpus = (ARTIFACTS / "corpus.md").read_bytes()
    (project / "README.md").write_bytes(corpus)
    catalog = project / "docatlas.project-docs.yaml"
    catalog.write_text(json.dumps({"schema_version": 1, "code_files": [], "documents": [
        {"path": "README.md", "role": "overview", "scope": "project",
         "description": "DocAtlas main-flow logging and evaluation documentation",
         "authority": "source_of_truth"}]}))
    for args in (("init", "-q"), ("config", "user.email", "comparison@example.test"),
                 ("config", "user.name", "DocAtlas comparison"), ("add", "."),
                 ("commit", "-qm", "Frozen identical comparison corpus")):
        subprocess.run(["git", "-C", str(project), *args], check=True)
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if k in os.environ}
    for key, name in {"HOME": "user-home", "USERPROFILE": "user-home",
                      "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                      "XDG_CACHE_HOME": "cache", "DOCATLAS_HOME": "docatlas-home"}.items():
        folder = isolated / name
        folder.mkdir(mode=0o700, exist_ok=True)
        env[key] = str(folder)
    env.update(PYTHONPATH=str(ROOT), PYTHONNOUSERSITE="1", DOCATLAS_AUTO_VECTORS="0",
               DOCATLAS_OFFLINE="1", DOCATLAS_REGISTRY_API_URL="http://127.0.0.1:1", NO_PROXY="*")
    database = Path(env["DOCATLAS_HOME"]) / "mcp-members" / "members.db"
    entry = read_project_docs_catalog(project).entries[0]
    mutation = {"operation": "sync_project_docs", "confirm": True, "storage_path": str(database),
                "expected_generation_id": None, "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
                "documents": [{"path": entry.path, "content_sha256": hashlib.sha256(corpus).hexdigest(),
                               "catalog_entry_hash": catalog_entry_hash(entry)}]}
    receipt = {"module": str(docmancer.__file__), "python": sys.executable,
               "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "corpus_sha256": hashlib.sha256(corpus).hexdigest(), "project": str(project),
               "transport": "MCP stdio, source checkout (not installed-wheel proof)", "results": []}
    output = ARTIFACTS / "docatlas-results.json"

    def save():
        output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "docmancer.cli", "--trace", "mcp", "docs-serve"], env=env, cwd=str(ROOT))
    with (ARTIFACTS / "docatlas-stderr.log").open("w") as errors:
        async with stdio_client(parameters, errlog=errors) as streams:
            async with ClientSession(*streams) as session:
                receipt["initialize"] = (await session.initialize()).model_dump(mode="json")
                receipt["tools"] = (await session.list_tools()).model_dump(mode="json")
                receipt["preparation"] = decode(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(project), "mutation": mutation}))
                save()
                if receipt["preparation"].get("status") != "success":
                    print(json.dumps(receipt["preparation"], ensure_ascii=False))
                    raise RuntimeError("MCP preparation failed; no question scores generated")
                for row in json.loads((ARTIFACTS / "questions.json").read_text()):
                    started = time.perf_counter()
                    response = await session.call_tool("get_docs_context", {
                        "question": row["question"], "project_path": str(project), "scope": "project"})
                    result = {"id": row["id"], "question": row["question"],
                              "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                              "response": response.model_dump(mode="json"), "payload": decode(response)}
                    receipt["results"].append(result)
                    save()
                    print(row["id"], result["payload"].get("status"), result["elapsed_ms"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
