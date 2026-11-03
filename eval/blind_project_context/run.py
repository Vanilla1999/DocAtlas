"""Run every sealed case through the real stdio MCP server (integration only).

    python eval/blind_project_context/run.py OUT [--source-tree DIR] [--jobs N]
        [--corpus L0|L2]... [--split dev|holdout]... [--case ID]...
        [--no-observer] [--env KEY=VALUE]...

For each corpus and shard: rebuild the frozen corpus from git objects, start a
fresh server process (``observed_server.py``) with isolated HOME/DOCATLAS_HOME,
read the unprepared answer, prepare through ``prepare_docs`` with an explicit
member grant built from the files on disk, then ask each case exactly as an
OpenCode client with the installed default environment would: ``project_path``,
``question`` and, for Russian cases only, ``search_question``. Nothing is
mocked; docmancer comes from ``--source-tree`` (default: this checkout).

OUT receives run.json (environment, timings, observer events per case), raw
payloads under payloads/<corpus>/ and server logs; score.py reads it.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from corpus import CATALOG, CORPORA, build  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash  # noqa: E402
from docmancer.docs.project_docs_catalog import read_project_docs_catalog  # noqa: E402
from docmancer.mcp.agent_config import OPENCODE_MCP_ENVIRONMENT  # noqa: E402

CALL_TIMEOUT = timedelta(minutes=15)
# Supported per-project setting (ProjectSourceBoundaryConfig.scan_deadline_seconds,
# product default 5 s). It bounds wall-clock time of member preparation and of
# catalog discovery only; preparing the 489 L2 members exceeds 5 s on a 2-CPU
# machine ("member deadline exhausted before chunk read"). The observer still
# reports any discovery truncation, which makes a run invalid.
SCAN_DEADLINE_SECONDS = 300
# The local project identity is a hash of the absolute project path and is
# part of every payload; a fixed work root keeps it equal across machines and
# checkouts. Evidence refs still differ between independent preparations, and
# they order rows with equal path and lines, so such rows may come in another
# order; score.py and the tests compare delivered rows as sets.
WORK_ROOT = Path("/tmp/docatlas-blind-project-context") if os.name == "posix" else Path(tempfile.gettempdir()) / "docatlas-blind-project-context"
MARKER = ".docatlas-blind-work"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_cases() -> list[dict]:
    return json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["cases"]


def server_env(root: Path, tree: Path, observer_log: Path | None, extra: dict[str, str],
               facts: Path | None = None) -> dict[str, str]:
    """Installed OpenCode registration environment, isolated and offline."""
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
    for key, name in {"HOME": "home", "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                      "XDG_CACHE_HOME": "cache", "DOCATLAS_HOME": "docatlas-home"}.items():
        (root / name).mkdir(mode=0o700, exist_ok=True)
        env[key] = str(root / name)
    env.update(OPENCODE_MCP_ENVIRONMENT)
    env.update(DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0", PYTHONNOUSERSITE="1",
               NO_PROXY="*", HF_HUB_OFFLINE="1", PYTHONPATH=str(tree))
    env.update(extra)
    if observer_log is not None:
        env["BLIND_OBSERVER_LOG"] = str(observer_log)
        if facts is not None:
            env["BLIND_OBSERVER_FACTS"] = str(facts)
    return env


def observer_facts(work: Path) -> Path:
    """Gold quotes for the passive observer only; the server's answer never sees them."""
    oracle = json.loads((HERE / "oracle.json").read_text(encoding="utf-8"))
    path = work / "observer-facts.json"
    path.write_text(json.dumps([{"fact_id": fact["fact_id"], "quote": fact["quote"]}
                                for topic in oracle["topics"] for fact in topic["facts"]],
                               ensure_ascii=False), encoding="utf-8")
    return path


def git_state(tree: Path) -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=tree, capture_output=True, text=True).stdout
    return {"commit": git("rev-parse", "HEAD").strip() or None,
            "dirty_paths": [line[3:] for line in git("status", "--porcelain").splitlines() if line.strip()]}


def member_grant(project: Path, storage_path: str) -> dict:
    """The explicit grant an agent builds from the catalog and the files on disk."""
    catalog = read_project_docs_catalog(project)
    if not (catalog.present and catalog.valid and catalog.entries):
        raise RuntimeError(f"invalid catalog in {project}")
    return {"operation": "sync_project_docs", "confirm": True, "storage_path": storage_path,
            "catalog_sha256": sha256((project / CATALOG).read_bytes()), "expected_generation_id": None,
            "documents": [{"path": entry.path, "content_sha256": sha256((project / entry.path).read_bytes()),
                           "catalog_entry_hash": catalog_entry_hash(entry)} for entry in catalog.entries]}


def payload_of(reply) -> tuple[dict, str]:
    if len(reply.content) != 1 or reply.content[0].type != "text":
        raise RuntimeError("expected exactly one text content item")
    text = reply.content[0].text
    return json.loads(text), text


def read_events(log: Path | None, offset: int) -> tuple[list[dict], int]:
    if log is None or not log.exists():
        return [], offset
    with log.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()], offset + len(data)


async def run_unit(unit: dict, out: Path, work: Path, tree: Path, observe: bool, extra: dict[str, str]) -> dict:
    root = work / unit["name"]
    project = root / "project"
    shutil.copytree(work / "corpora" / unit["corpus"] / "project", project)
    if unit["scan_deadline"]:
        (project / "docatlas.yaml").write_text(
            f"project:\n  scan_deadline_seconds: {unit['scan_deadline']}\n", encoding="utf-8")
    log = (out / "logs" / f"{unit['name']}.observer.jsonl") if observe else None
    env = server_env(root, tree, log, extra, (work / "observer-facts.json") if observe else None)
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "observed_server.py")],
                                   env=env, cwd=str(root))
    payload_dir = out / "payloads" / unit["corpus"]
    payload_dir.mkdir(parents=True, exist_ok=True)
    records, offset = [], 0
    with (out / "logs" / f"{unit['name']}.server.stderr").open("w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as streams:
            async with ClientSession(*streams, read_timeout_seconds=CALL_TIMEOUT) as session:
                await session.initialize()
                tools = {tool.name for tool in (await session.list_tools()).tools}
                if not {"get_docs_context", "prepare_docs"} <= tools:
                    raise RuntimeError(f"server tools missing: {sorted(tools)}")
                cold, _ = payload_of(await session.call_tool("get_docs_context", {
                    "project_path": str(project), "question": unit["cases"][0]["question"]}))
                if cold.get("status") != "not_prepared" or not cold.get("storage_path"):
                    raise RuntimeError(f"unexpected cold answer: {json.dumps(cold)[:600]}")
                started = time.perf_counter()
                prepared, _ = payload_of(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(project),
                    "mutation": member_grant(project, cold["storage_path"])}))
                prepare_seconds = time.perf_counter() - started
                if prepared.get("status") != "success":
                    raise RuntimeError(f"prepare failed: {json.dumps(prepared)[:600]}")
                _, offset = read_events(log, 0)
                for case in unit["cases"]:
                    arguments = {"project_path": str(project), "question": case["question"]}
                    if case.get("search_question"):
                        arguments["search_question"] = case["search_question"]
                    started = time.perf_counter()
                    reply = await session.call_tool("get_docs_context", arguments)
                    seconds = time.perf_counter() - started
                    text = reply.content[0].text if reply.content and reply.content[0].type == "text" else ""
                    (payload_dir / f"{case['id']}.json").write_text(text, encoding="utf-8")
                    events, offset = read_events(log, offset)
                    records.append({"case_id": case["id"], "corpus": unit["corpus"], "unit": unit["name"],
                                    "seconds": round(seconds, 3), "is_error": bool(reply.isError),
                                    "payload": f"payloads/{unit['corpus']}/{case['id']}.json",
                                    "payload_sha256": sha256(text.encode("utf-8")),
                                    "utf8_bytes": len(text.encode("utf-8")), "observer_events": events})
                    print(f"{unit['name']} {case['id']} {seconds:.1f}s", flush=True)
    shown = {key: value for key, value in env.items()
             if key not in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "BLIND_OBSERVER_LOG",
                            "BLIND_OBSERVER_FACTS")
             and not key.endswith("_HOME") and key != "PYTHONPATH"}
    return {"name": unit["name"], "corpus": unit["corpus"], "project_path": str(project), "server_environment": shown,
            "prepare_seconds": round(prepare_seconds, 3), "prepared_documents": len(member_grant(project, "")["documents"]),
            "cold_reason_code": cold.get("reason_code"), "records": records}


async def run_all(units: list[dict], jobs: int, out: Path, work: Path, tree: Path, observe: bool,
                  extra: dict) -> list[dict]:
    async def worker(index: int) -> list[dict]:
        return [await run_unit(unit, out, work, tree, observe, extra) for unit in units if unit["worker"] == index]
    return [result for group in await asyncio.gather(*(worker(index) for index in range(jobs))) for result in group]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--source-tree", type=Path, default=ROOT)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--corpus", action="append", choices=CORPORA)
    parser.add_argument("--split", action="append", choices=("dev", "holdout"))
    parser.add_argument("--case", action="append")
    parser.add_argument("--no-observer", action="store_true")
    parser.add_argument("--env", action="append", default=[], help="extra server variable KEY=VALUE")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--work-root", type=Path, default=WORK_ROOT,
                        help="fixed scratch root for projects and stores (default %(default)s); recreated per run")
    parser.add_argument("--scan-deadline", type=float, default=SCAN_DEADLINE_SECONDS,
                        help="project docatlas.yaml project.scan_deadline_seconds; 0 writes no docatlas.yaml")
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error(f"{out} must be new or empty")
    tree = args.source_tree.resolve()
    extra = dict(item.split("=", 1) for item in args.env)
    cases = [case for case in load_cases()
             if (not args.split or case["split"] in args.split) and (not args.case or case["id"] in args.case)]
    if not cases:
        parser.error("no cases selected")
    corpora = args.corpus or list(CORPORA)
    jobs = max(1, args.jobs)
    topic_order = list(dict.fromkeys(case["topic_id"] for case in cases))
    shards = [[case for case in cases if topic_order.index(case["topic_id"]) % jobs == shard] for shard in range(jobs)]
    deadline = int(args.scan_deadline) if float(args.scan_deadline).is_integer() else args.scan_deadline
    units = [{"name": f"{corpus}-{shard}", "corpus": corpus, "worker": shard, "cases": shards[shard],
              "scan_deadline": deadline} for corpus in corpora for shard in range(jobs) if shards[shard]]
    (out / "logs").mkdir(parents=True, exist_ok=True)
    work = args.work_root
    lock = open(str(work) + ".lock", "w")
    try:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        pass
    except OSError:
        parser.error(f"another run is using {work}")
    if work.exists():
        if not (work / MARKER).exists():
            parser.error(f"{work} exists and was not created by this runner")
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / MARKER).write_text("scratch directory of eval/blind_project_context/run.py\n", encoding="utf-8")
    build(work / "corpora")
    if not args.no_observer:
        observer_facts(work)
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    results = asyncio.run(run_all(units, jobs, out, work, tree, not args.no_observer, extra))
    env_shown = results[0]["server_environment"] if results else {}
    run = {"schema_version": 1, "started_at_utc": started_at.isoformat(timespec="seconds"),
           "wall_seconds": round(time.perf_counter() - started, 1),
           "source_tree": git_state(tree), "eval_tree": git_state(ROOT),
           "questions_sha256": sha256((HERE / "questions.json").read_bytes()),
           "python": sys.version.split()[0], "platform": platform.platform(), "cpus": os.cpu_count(),
           "jobs": jobs, "observer": not args.no_observer, "work_root": str(work), "server_environment": env_shown,
           "observer_oracle_sha256": None if args.no_observer else sha256((HERE / "oracle.json").read_bytes()),
           "project_config": {"docatlas.yaml": {"project": {"scan_deadline_seconds": deadline}}} if deadline else None,
           "selected_cases": [case["id"] for case in cases], "corpora": corpora,
           "units": [{key: value for key, value in result.items() if key not in ("records", "server_environment")}
                     for result in results],
           "records": [record for result in results for record in result["records"]]}
    (out / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not args.keep_work:
        shutil.rmtree(work)
    print(f"wrote {out / 'run.json'}: {len(run['records'])} answers in {run['wall_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
