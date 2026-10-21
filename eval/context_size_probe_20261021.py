"""Real installed MCP: actual off/on context volume on unseen EN/RU questions."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from datetime import timedelta

MAIN_SHA = "f8e17489733798c731f6b9c555adaee48b92fbf3"
QUESTIONS = {
 "black": [
  ("en_target", "If I omit --target-version, how does Black decide which Python versions to support?"),
  ("ru_target", "Как Black выбирает целевые версии Python, если не указать --target-version?"),
  ("en_other", "What precisely changes when Black is invoked with --no-cache?"),
  ("unsupported", "Does Black document a guaranteed 99th-percentile runtime for formatting a file?")],
 "poetry": [
  ("en_target", "How can a Poetry application configuration key be represented as an environment variable?"),
  ("ru_target", "Как преобразовать ключ конфигурации Poetry в имя переменной окружения?"),
  ("en_other", "How can I undo a Python environment that I previously selected with Poetry?"),
  ("unsupported", "What hard upper bound does Poetry guarantee for dependency solver response time?")],
 "textual": [
  ("en_target", "What arguments does a Textual watch handler receive if it declares one or two parameters?"),
  ("ru_target", "Какие параметры получает обработчик watch в Textual, если он принимает один или два аргумента?"),
  ("en_other", "How does a Textual worker running in a thread safely modify a widget?"),
  ("unsupported", "Does Textual state a guaranteed maximum keyboard-to-render delay?")],
 "vite": [
  ("en_target", "When a variable exists in both the process and a Vite .env file, which has priority?"),
  ("ru_target", "Если переменная задана процессом и файлом .env в Vite, что имеет приоритет?"),
  ("en_other", "What happens when strictPort is enabled and the Vite dev-server port is occupied?"),
  ("unsupported", "Does Vite guarantee a precise production CDN cache time-to-live?")],
 "eslint": [
  ("en_target", "Which paths are ignored by default by ESLint flat config?"),
  ("ru_target", "Какие пути ESLint игнорирует по умолчанию в flat config?"),
  ("en_other", "Which flat-config filenames are supported by ESLint?"),
  ("unsupported", "What guaranteed service uptime SLA does ESLint provide for linting locally?")],
}

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

def worker(args):
    runtime = load_module("probe_runtime", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load_module("probe_helper", args.repo / "eval/prepared_model_comparison40/run.py")
    from docmancer.mcp._docs_server_part01 import _run_async
    corpus = args.repo / "eval/prepared_model_comparison40"
    families = json.loads((corpus / "source_plan.json").read_text())["families"]
    fam = next(f for f in families if f["id"] == args.family)
    root = args.work / args.mode / args.family / "project"
    docs = {p: (corpus / "sources" / args.family / p).read_text(encoding="utf-8") for p in fam["paths"]}
    runtime.write_project(root, docs)
    with runtime.isolated_service(args.work / args.mode / args.family / "state") as (service, cfg):
        inventory = runtime.index_project(service, cfg, root)
        before = (helper.logical_state(inventory), helper.source_state(root))
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION=("minilm-sections-v1" if args.mode == "minilm" else "off"),
                          DOCATLAS_CONTEXT_ABSTENTION="off", DOCATLAS_MCP_TEXT_FALLBACK="1",
                          DOCATLAS_MINILM_MODEL_DIR=str(args.model), HF_HUB_OFFLINE="1")
        try:
            asyncio.run(_run_async(service))
        finally:
            state = (helper.logical_state(inventory), helper.source_state(root))
            save(args.out / args.mode / args.family / "state-check.json",
                 {"source_files_unchanged": before[1] == state[1],
                  "logical_database_unchanged": before[0] == state[0],
                  "source_files": list(docs)})

async def query_server(args, mode, family):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    path = args.out / mode / family
    path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(DOCATLAS_CONTEXT_COMPRESSION="off", DOCATLAS_CONTEXT_ABSTENTION="off")
    params = StdioServerParameters(command=sys.executable,
       args=["-I", str(Path(__file__).resolve()), "--worker", "--mode", mode, "--family", family,
             "--repo", str(args.repo), "--work", str(args.work), "--out", str(args.out),
             "--model", str(args.model)], env=env)
    records = []
    with (path / "stderr.log").open("w") as err:
      async with stdio_client(params, errlog=err) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=180)) as session:
          await session.initialize()
          for label,question in QUESTIONS[family]:
            req = {"question": question,
                   "project_path": str(args.work / mode / family / "project"), "scope": "project"}
            begun = time.perf_counter()
            reply = await session.call_tool("get_docs_context", req)
            elapsed = round(time.perf_counter() - begun, 3)
            assert len(reply.content) == 1 and reply.content[0].type == "text", reply
            wire = reply.content[0].text
            raw = json.loads(wire)
            expanded = expand_sections(raw)
            assert reply.structuredContent is None
            assert not reply.isError, str(expanded)[:800]
            assert bool(raw.get("context_format") == "docatlas.sections.v1") == (mode == "minilm")
            assert expanded.get("kind") == "docs_context" and expanded.get("sources")
            content = wire.encode("utf-8")
            tokens = projection_token_count(content)
            rows = expanded["sources"]
            groups = sorted({(r.get("path_or_url"), r.get("section")) for r in rows})
            record = {"family": family, "variant": label, "language": "ru" if label.startswith("ru") else "en",
                      "question": question, "mode": mode, "status": expanded.get("status"),
                      "sources": len(rows), "groups": len(groups),
                      "total_snippet_characters": sum(len(r["snippet"]) for r in rows),
                      "wire_bytes": len(content), "tokens_o200k": tokens,
                      "budget_proxy": max(tokens, math.ceil(len(content) / 4)),
                      "time_s": elapsed,
                      "selected_groups": [{"file": p, "section": s} for p,s in groups],
                      "id_hash": hashlib.sha256(json.dumps([r["evidence_id"] for r in rows]).encode()).hexdigest(),
                      "snippet_first": rows[0]["snippet"][:220]}
            save(path / f"{label}-record.json", record)
            (path / f"{label}-wire.json").write_bytes(content)
            save(path / f"{label}-expanded.json", expanded)
            records.append(record)
            print(json.dumps({"mode":mode, "family":family, "q":label,
                              "tokens":tokens, "sources":len(rows), "groups":len(groups),
                              "seconds":elapsed}), flush=True)
    state = json.loads((path/"state-check.json").read_text())
    assert state["source_files_unchanged"] and state["logical_database_unchanged"], state
    return records

async def main(args):
    import docmancer
    product = Path(docmancer.__file__).resolve().parent
    assert not product.is_relative_to(args.repo), "must be installed wheel"
    assert all((args.repo / "docmancer" / str(p.relative_to(product))).read_bytes() == p.read_bytes()
               for p in product.rglob("*.py")), "installed wheel/source mismatch"
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    save(args.out / "FREEZE.json", {"product_base_sha":MAIN_SHA,
       "audit_checkout":os.getenv("TESTED_SHA"), "questions":QUESTIONS, "oracle_used":False,
       "client":"real stdio MCP text fallback=1"})
    records=[]
    for mode in ("off","minilm"):
      for group in QUESTIONS:
        records.extend(await query_server(args,mode,group))
    by={(r["family"], r["variant"], r["mode"]):r for r in records}
    joined=[]
    for family, items in QUESTIONS.items():
      for label,_ in items:
        a,b=(by[(family,label,m)] for m in ("off","minilm"))
        baseline=json.loads((args.out/"off"/family/f"{label}-expanded.json").read_text())
        reduced=json.loads((args.out/"minilm"/family/f"{label}-expanded.json").read_text())
        from collections import Counter
        old=Counter((r.get("path_or_url"),r.get("section"),r.get("snippet")) for r in baseline["sources"])
        selected=Counter((r.get("path_or_url"),r.get("section"),r.get("snippet")) for r in reduced["sources"])
        assert not (selected-old), "selected exact snippets must originate from the same indexed corpus"
        assert b["groups"]<=5
        joined.append({"family":family,"variant":label,"question":a["question"],
          "default_tokens":a["tokens_o200k"],"minilm_tokens":b["tokens_o200k"],
          "default_sources":a["sources"],"minilm_sources":b["sources"],
          "minilm_groups":b["groups"],"saved_percent":round(100*(1-b["tokens_o200k"]/a["tokens_o200k"]),1),
          "selected_groups":b["selected_groups"]})
    save(args.out/"ROWS.json",joined)
    summary={"product_base_sha":MAIN_SHA,"audit_sha":os.getenv("TESTED_SHA"),
      "new_queries":len(joined),"actual_mcp_calls":len(records),
      "default_mean_tokens":round(statistics.mean(j["default_tokens"] for j in joined),1),
      "minilm_mean_tokens":round(statistics.mean(j["minilm_tokens"] for j in joined),1),
      "minilm_max_tokens":max(j["minilm_tokens"] for j in joined),
      "minilm_max_groups":max(j["minilm_groups"] for j in joined),
      "en_ru_top5_group_overlap":{},"no_oracle_quality_claim":True}
    for family in QUESTIONS:
      a=set((r["file"],r["section"]) for r in by[(family,"en_target","minilm")]["selected_groups"])
      b=set((r["file"],r["section"]) for r in by[(family,"ru_target","minilm")]["selected_groups"])
      summary["en_ru_top5_group_overlap"][family]={"intersection":len(a&b),"union":len(a|b)}
    save(args.out/"SUMMARY.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2), flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for flag in ("repo","work","out","model"):
      parser.add_argument("--"+flag,type=Path,required=True)
    parser.add_argument("--mode",choices=("off","minilm"))
    parser.add_argument("--family",choices=tuple(QUESTIONS))
    parser.add_argument("--worker",action="store_true")
    args=parser.parse_args()
    for key in ("repo","work","out","model"):
      setattr(args,key,getattr(args,key).resolve())
    if args.worker: worker(args)
    else: asyncio.run(main(args))
