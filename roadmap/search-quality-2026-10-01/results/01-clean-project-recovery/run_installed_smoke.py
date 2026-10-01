"""One-shot installed-wheel stdio reproduction; never clears an existing index."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import tempfile

import docmancer
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


QUESTION = "How do I prepare local project documentation?"
README = (
    "# Local project documentation\n\n"
    'To prepare local project documentation, call prepare_docs(action="sync_project_docs"). '
    "This indexes repository docs before retrieval.\n"
)


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def payload(response):
    if isinstance(response.structuredContent, dict):
        return response.structuredContent
    for block in response.content:
        if getattr(block, "type", None) == "text":
            try:
                value = json.loads(block.text)
            except ValueError:
                continue
            if isinstance(value, dict):
                return value
    raise AssertionError("No structured or JSON MCP payload")


async def run(args) -> None:
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    checkout = Path(args.checkout).resolve()
    baseline_commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{args.baseline_commit}^{{commit}}"],
        cwd=checkout, text=True,
    ).strip()
    installed = Path(docmancer.__file__).resolve().parent
    assert "site-packages" in installed.parts and installed != checkout / "docmancer", installed
    production = {}
    for source in sorted((checkout / "docmancer").rglob("*.py")):
        relative = source.relative_to(checkout / "docmancer")
        reference = (
            subprocess.check_output(["git", "show", f"{baseline_commit}:docmancer/{relative}"], cwd=checkout)
            if args.phase == "before" else source.read_bytes()
        )
        assert (installed / relative).read_bytes() == reference, relative
        production[str(relative)] = hashlib.sha256(reference).hexdigest()
    save(out / "runtime.json", {
        "version": importlib.metadata.version("doc-atlas"),
        "module": str(installed),
        "executable": str(Path(args.executable).resolve()),
        "checkout_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=checkout, text=True,
        ).strip(),
        "production_reference": baseline_commit if args.phase == "before" else "working_tree",
        "production_diff_sha256": hashlib.sha256(
            b"" if args.phase == "before" else subprocess.check_output(
                ["git", "diff", "--", "docmancer"], cwd=checkout,
            )
        ).hexdigest(),
        "production_file_hashes": production,
        "transport": "installed console script over MCP stdio",
    })

    work = Path(tempfile.mkdtemp(prefix=f"p0-{args.phase}-", dir="/tmp/opencode"))
    root = work / "repo"
    root.mkdir()
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "docatlas.yaml").write_text(
        "index:\n  provider: sqlite\n  db_path: .docatlas/docatlas.db\n"
        "  extracted_dir: .docatlas/extracted\n", encoding="utf-8",
    )
    (root / ".gitignore").write_text(".docatlas/\n", encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "README.md", "docatlas.yaml", ".gitignore"],
        ["git", "-c", "user.name=P0 Smoke", "-c", "user.email=smoke@example.invalid",
         "commit", "-qm", "Freeze project docs"],
    ):
        subprocess.run(command, cwd=root, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    save(out / "fixture.json", {"root": str(root), "head": head, "initial_git_status": "clean"})

    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("DOCATLAS_", "DOCMANCER_"))
        and key != "PYTHONPATH" and not key.endswith("API_KEY")
    }
    env.update(DOCATLAS_HOME=str(work / "home"), DOCATLAS_OFFLINE="1",
               DOCATLAS_AUTO_VECTORS="0", DO_NOT_TRACK="1")
    params = StdioServerParameters(
        command=str(Path(args.executable).resolve()), args=["mcp", "docs-serve"],
        cwd=str(work), env=env,
    )
    with (out / "stderr.log").open("w", encoding="utf-8") as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write) as session:
                save(out / "initialize.json", (await session.initialize()).model_dump(mode="json", by_alias=True))

                async def call(name, arguments, label):
                    response = await asyncio.wait_for(session.call_tool(name, arguments), timeout=120)
                    save(out / f"{label}.json", {
                        "tool": name, "request": arguments,
                        "wire": response.model_dump(mode="json", by_alias=True),
                    })
                    assert not response.isError
                    return payload(response)

                status_args = {"action": "project", "project_path": str(root), "details": True}
                status = await call("docs_status", status_args, "status-before")
                assert status["project"]["reason_code"] == "project_docs_found_not_indexed"
                request = {"question": QUESTION, "project_path": str(root), "scope": "all"}
                context = await call("get_docs_context", request, "context-before-sync")
                assert context["status"] == "insufficient_evidence"
                action = context["recommended_next_action"]
                after_read = await call("docs_status", status_args, "status-after-read")
                assert after_read["project"]["reason_code"] == "project_docs_found_not_indexed"
                assert after_read["project"]["source_summary"]["indexed"] == 0
                if args.phase == "before":
                    assert context["recovery_reason_code"] == "no_candidates"
                    assert action["tool"] == "code_search"
                else:
                    assert context["recovery_reason_code"] == "project_docs_found_not_indexed"
                    assert action["tool"] == "prepare_docs"
                    assert action["requires_confirmation"] is False
                    assert action["auto_execute"] is False
                    assert action["arguments_patch"] == {
                        "action": "sync_project_docs", "project_path": str(root),
                        "with_vectors": False,
                        "plan_digest": hashlib.sha256(f"clean_git_auto:{head}".encode()).hexdigest(),
                    }
                    draft = root / "draft.txt"
                    draft.write_text("untracked draft\n", encoding="utf-8")
                    blocked = await call(action["tool"], action["arguments_patch"], "dirty-sync-blocked")
                    assert blocked["status"] == "precondition_failed"
                    assert blocked["requires_confirmation"] is True
                    blocked_status = await call("docs_status", status_args, "status-after-blocked-sync")
                    assert blocked_status["project"]["source_summary"]["indexed"] == 0
                    draft.unlink()  # Only the smoke's own newly created fixture file.
                    prepared = await call(action["tool"], action["arguments_patch"], "sync")
                    assert prepared["status"] == "success"
                    retried = await call("get_docs_context", request, "context-after-sync")
                    assert retried["status"] == "ok" and retried["context_available"] is True
                    assert retried["answer_supported"] is False
                    assert any(
                        source["path_or_url"] == "README.md"
                        and source["snippet"] in README
                        and "sync_project_docs" in source["snippet"]
                        for source in retried["sources"]
                    )
                    final_status = await call("docs_status", status_args, "status-after-sync")
                    assert final_status["project"]["reason_code"] == "project_docs_ready"
                    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    result = {"status": "PASS", "phase": args.phase, "recovery_tool": action["tool"],
              "recovery_reason_code": context["recovery_reason_code"], "fixture": str(root)}
    save(out / "result.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--baseline-commit", default="5cd7515c")
    parser.add_argument("--executable", required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--output", required=True)
    asyncio.run(run(parser.parse_args()))
