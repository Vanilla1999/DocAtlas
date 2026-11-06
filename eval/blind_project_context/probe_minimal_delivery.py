"""Installed stdio replay of unchanged T01, trace parity and live capabilities."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from run import server_env
from docmancer.mcp.project_binding import make_binding
from docmancer.docs.application.context_assembly import decode_context
from docmancer.docs.application.projection_tokenizer import projection_token_count


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--recipe", default="complete-maxp-token-overlap-v1",
                         choices=("complete-maxp-token-overlap-v1", "complete-own-body-gated-maxp-v2",
                                  "complete-fit-first-maxp-v4"))
    single = parser.add_mutually_exclusive_group()
    single.add_argument("--original-only", action="store_true",
                         help="One unchanged original request; do not claim OFF/ON or resource-read proof")
    single.add_argument("--translated-only", action="store_true",
                        help="One unchanged original plus frozen complete translation; no parity/source-read proof")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    tree = Path(__file__).resolve().parents[2]
    env = server_env(args.prepared, tree, None, {
        "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "1", "DOCATLAS_CONTEXT_COMPRESSION": "off",
        "DOCATLAS_EXPERIMENT_MINI_PATH": str(args.model_dir),
        "DOCATLAS_MINIMAL_CONTEXT_POLICY": str(args.policy),
        "DOCATLAS_MINIMAL_CONTEXT_RECIPE": args.recipe,
    })
    env.pop("PYTHONPATH", None)
    env["DOCATLAS_PROJECT_BINDING"] = json.dumps(make_binding(args.prepared / "project", args.prepared / "project"))
    question = "Что от меня ожидается, когда я отправляю pull request в DocAtlas?"
    translation = "What is expected of me when I submit a pull request to DocAtlas?"
    facts = ["Branch name: `feat/<topic>` or `fix/<description>`",
             "Run the full test suite before opening the PR",
             "New connectors or fetchers should include tests where practical"]
    source = (args.prepared / "project/CONTRIBUTING.md").read_bytes().decode()
    assert all(fact in source for fact in facts)
    watched = list((args.prepared / "project").rglob("*.md")) + list((args.prepared / "docatlas-home").rglob("*.db"))
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    packets, receipts, calls = {}, [], 0
    single_request = args.original_only or args.translated_only
    for observed in ((False,) if single_request else (False, True)):
        lane = "observed" if observed else "plain"
        current_env = dict(env)
        if observed:
            current_env["DOCATLAS_TRACE"] = "1"
        params = StdioServerParameters(command=str(args.executable), args=["mcp", "docs-serve"],
                                      env=current_env, cwd=str(args.prepared))
        with (args.out / f"{lane}.stderr").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    requests = [(lane, {"question": question})]
                    if args.translated_only:
                        requests = [("translated", {"question": question, "search_question": translation})]
                    if not observed and not single_request:
                        requests.extend([("translated", {"question": question, "search_question": translation}),
                                         ("focused", {"question": question, "source_path": "CONTRIBUTING.md"})])
                    for name, request in requests:
                        started = time.perf_counter()
                        response = await session.call_tool("get_docs_context", request)
                        calls += 1
                        assert response.structuredContent is None and len(response.content) == 1
                        text = response.content[0].text
                        packets[name] = response.model_dump(mode="json")
                        (args.out / f"{name}.json").write_text(json.dumps(packets[name], ensure_ascii=False, indent=2))
                        packet = json.loads(text)
                        view = decode_context(packet) if packet.get("context_format") else packet
                        rows = view.get("sources", [])
                        for row in rows:
                            path = args.prepared / "project" / row["path"]
                            raw = path.read_bytes().decode()
                            assert row["text"] in raw
                            expected = "".join(raw.splitlines(keepends=True)[row["line_start"] - 1:row["line_end"]])
                            assert row["text"] == expected
                            # Public content_sha256 binds canonical source
                            # material, not just snippet bytes. These frozen
                            # project catalogs have no version declaration.
                            material = {"path": row["path"], "section": row["section"],
                                        "content": expected, "snippet": expected, "version": None}
                            encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                            assert hashlib.sha256(encoded).hexdigest() == row["content_sha256"]
                        delivered = "\n".join(row["text"] for row in rows)
                        record = {"lane": name, "seconds": time.perf_counter() - started,
                                  "tokens": projection_token_count(text.encode()), "rows": len(rows),
                                  "facts": [fact in delivered for fact in facts],
                                  "reason_code": view.get("reason_code"), "selection": view.get("source_selection")}
                        receipts.append(record)
                        if name == "focused" and rows:
                            uri = rows[-1]["source_uri"]
                            resource = await session.call_tool("read_docs_source", {"uri": uri})
                            replay = await session.call_tool("read_docs_source", {"uri": uri})
                            calls += 2
                            resource_data = json.loads(resource.content[0].text)
                            replay_data = json.loads(replay.content[0].text)
                            assert replay_data.get("reason_code") == "unknown_or_expired_reference"
                            (args.out / "source-read.json").write_text(json.dumps(resource_data, ensure_ascii=False, indent=2))
    if not single_request:
        assert packets["plain"] == packets["observed"], "Observer changed delivered packet"
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    assert before == after, "Read changed frozen source/SQLite bytes"
    report = {"boundary": "installed_stdio", "requests": calls,
               "trace_parity": None if single_request else True,
              "recipe": args.recipe, "read_only": True, "calls": receipts,
              "all_three_facts_original": all(receipts[0]["facts"]),
              "policy_sha256": hashlib.sha256(args.policy.read_bytes()).hexdigest()}
    (args.out / "receipt.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
