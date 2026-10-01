"""Clear/rebuild in one installed MCP process per configuration mode."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

import docmancer
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


QUESTION = "How do I prepare local project documentation?"
README = '# Local documentation\n\nTo prepare local project documentation, call prepare_docs(action="sync_project_docs").\n'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


async def run(args):
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    checkout = Path(args.checkout).resolve()
    installed = Path(docmancer.__file__).resolve().parent
    assert "site-packages" in installed.parts
    hashes = {}
    for source in (checkout / "docmancer").rglob("*.py"):
        relative = source.relative_to(checkout / "docmancer")
        expected = (subprocess.check_output(["git", "show", f"a45d2817:docmancer/{relative}"], cwd=checkout)
                    if args.phase == "before" else source.read_bytes())
        assert (installed / relative).read_bytes() == expected, relative
        hashes[str(relative)] = hashlib.sha256(expected).hexdigest()
    save(output / "runtime.json", {
        "version": importlib.metadata.version("doc-atlas"), "import_path": str(installed),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip(),
        "reference": "a45d2817" if args.phase == "before" else "working_tree",
        "production_hashes": hashes, "executable": args.executable,
    })
    for mode in ("default", "explicit"):
        out = output / mode
        out.mkdir()
        work = Path(tempfile.mkdtemp(prefix=f"clear-rebuild-{mode}-", dir="/tmp/opencode"))
        projects = []
        for name in ("target", "other"):
            root = work / name
            root.mkdir()
            (root / "README.md").write_text(README)
            (root / ".gitignore").write_text(".docatlas/\n")
            (root / "docatlas.yaml").write_text("index:\n  db_path: .docatlas/project.db\n  extracted_dir: .docatlas/extracted\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid", "commit", "-qm", "fixture"], cwd=root, check=True)
            projects.append(root)
        root, other = projects
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("DOCATLAS_", "DOCMANCER_")) and key != "PYTHONPATH" and not key.endswith("API_KEY")}
        env.update(DOCATLAS_HOME=str(work / "home"), DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0", DO_NOT_TRACK="1")
        command_args = ["mcp", "docs-serve"]
        if mode == "explicit":
            command_args += ["--config", str(root / "docatlas.yaml")]
        parameters = StdioServerParameters(command=args.executable, args=command_args, cwd=str(work), env=env)
        with (out / "stderr.log").open("w") as err:
            async with stdio_client(parameters, errlog=err) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    async def call(name, request, label):
                        wire = await asyncio.wait_for(session.call_tool(name, request), timeout=120)
                        save(out / f"{label}.json", {"request": request, "wire": wire.model_dump(mode="json", by_alias=True)})
                        result = wire.structuredContent
                        if not isinstance(result, dict):
                            result = json.loads(next(block.text for block in wire.content if block.type == "text"))
                        return result

                    async def sync(project, label):
                        return await call("prepare_docs", {"action": "sync_project_docs", "project_path": str(project), "with_vectors": False}, label)

                    async def query(project, label):
                        result = await call("get_docs_context", {"question": QUESTION, "project_path": str(project)}, label)
                        assert result["status"] == "ok", result
                        assert any(source["path_or_url"] == "README.md" and source["snippet"] in README for source in result["sources"])

                    assert (await sync(root, "sync-before"))["status"] == "success"
                    await query(root, "query-before")
                    if mode == "default":
                        assert (await sync(other, "other-sync"))["status"] == "success"
                        await query(other, "other-before")
                    preview = await call("prepare_docs", {"action": "clear_index", "scope": "project-local", "project_path": str(root)}, "preview")
                    assert preview["status"] == "confirmation_required"
                    assert (await call("prepare_docs", preview["arguments_patch"], "clear"))["status"] == "applied"
                    rebuilt = await sync(root, "sync-after")
                    if args.phase == "before":
                        assert rebuilt["status"] == "failed" and rebuilt["error"]["exception_type"] == "OperationalError", rebuilt
                    else:
                        assert rebuilt["status"] == "success", rebuilt
                        await query(root, "query-after")
                        if mode == "default":
                            await query(other, "other-after")
                        with sqlite3.connect(root / ".docatlas/project.db") as connection:
                            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        assert {"sources", "sections"} <= tables
                    assert (root / "README.md").read_text() == README
                    save(out / "result.json", {"status": "PASS", "phase": args.phase, "mode": mode, "same_session": True, "fixture": str(root)})
        print(f"PASS {args.phase} {mode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
