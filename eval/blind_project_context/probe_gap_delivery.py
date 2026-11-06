"""Three installed-stdio reads: hybrid trace parity and lexical comparison.

The existing observer only records counters; no annotations enter selection.
Run after run_gap_agent_study.py has written its explicit host configuration.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--focused", action="store_true", help="Also check a focused installed response and its issued continuation")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    server = json.loads(args.config.read_text())["mcp"]["servers"]["docatlas"]
    question = "Что от меня ожидается, когда я отправляю pull request в DocAtlas?"
    request = {"question": question, "search_question": "What is expected of me when I submit a pull request to DocAtlas?"}
    results = {}
    focused_receipt = None
    for lane in ("hybrid", "hybrid-observed", "lexical-observed"):
        env = dict(server["environment"])
        if lane.startswith("lexical"):
            env["DOCATLAS_EXPERIMENT_ACQUISITION_E5"] = "0"
        if lane.endswith("observed"):
            env["BLIND_OBSERVER_LOG"] = str(args.out / (lane + ".trace.jsonl"))
            command = str(args.python)
            command_args = [str(Path(__file__).with_name("observed_server.py"))]
        else:
            command, *command_args = server["command"]
        params = StdioServerParameters(command=command, args=command_args, env=env, cwd=server["cwd"])
        with (args.out / (lane + ".stderr")).open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    response = await session.call_tool("get_docs_context", request)
                    data = response.model_dump(mode="json")
                    assert not data.get("isError"), data
                    results[lane] = data
                    (args.out / (lane + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2))
                    if args.focused and lane == "hybrid":
                        from docmancer.docs.application.context_assembly import decode_context
                        from docmancer.docs.application.projection_tokenizer import projection_token_count
                        focused_args = {**request, "source_path": "CONTRIBUTING.md"}
                        focused = await session.call_tool("get_docs_context", focused_args)
                        wire = focused.content[0].text
                        packet = json.loads(wire)
                        rows = decode_context(packet)["sources"]
                        source = (Path(server["cwd"]) / "project/CONTRIBUTING.md").read_text()
                        assert rows and all(r["path"] == "CONTRIBUTING.md" and r["text"] in source for r in rows)
                        text = "\n".join(r["text"] for r in rows)
                        assert all(f in text for f in ("feat/<topic>", "full test suite", "connectors")), text
                        assert projection_token_count(wire.encode()) <= 2400
                        (args.out / "focused.json").write_text(focused.model_dump_json(indent=2))
                        more = packet["more_context"]
                        follow = await session.call_tool("get_docs_context", {
                            **focused_args, "portion": more.get("next_portion") or 2,
                            "continuation_token": more["continuation_token"]})
                        (args.out / "focused-continuation.json").write_text(follow.model_dump_json(indent=2))
                        next_packet = json.loads(follow.content[0].text)
                        assert not next_packet.get("error"), next_packet
                        if next_packet.get("context_format"):
                            next_rows = decode_context(next_packet).get("sources", [])
                        else:
                            assert next_packet.get("reason_code") == "context_portion_exhausted"
                            assert next_packet.get("sources") == []
                            next_rows = []
                        assert all(r["path"] == "CONTRIBUTING.md" and r["text"] in source for r in next_rows)
                        assert not ({r["ref"] for r in rows} & {r["ref"] for r in next_rows})
                        focused_receipt = {"tokens": projection_token_count(wire.encode()),
                                           "rows": len(rows), "next_rows": len(next_rows)}
    # The observer must preserve BOTH the machine packet and actual model text.
    assert results["hybrid"] == results["hybrid-observed"], "passive observer changed delivery"
    methods = {}
    for lane in ("hybrid-observed", "lexical-observed"):
        events = [json.loads(l) for l in (args.out / (lane + ".trace.jsonl")).read_text().splitlines()]
        calls = [e for e in events if e["event"] == "acquisition"]
        assert calls and all(e["returned_rows"] <= 256 for e in calls)
        methods[lane] = sorted({e["method"] for e in calls})
    assert methods["hybrid-observed"] == ["lexical_e5_round_robin_v1"]
    assert methods["lexical-observed"] == ["fts5_source_bm25_or_v2"]
    receipt = {"question": question, "requests": 5 if args.focused else 3,
               "focused": focused_receipt, "observer_delivery_parity": True, "methods": methods,
               "hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.iterdir() if p.is_file()}}
    (args.out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
