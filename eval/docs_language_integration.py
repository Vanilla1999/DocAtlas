"""Installed SQLite + public MCP language preflight and translated-question acceptance.

No mocked retrieval, ranking, storage or validator. Existing V40 witnesses are
loaded only after every delivered response. Controls use independent fixtures.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys

PAIRS = {
    "black": ("V40-B02", "Как Black определяет целевые версии Python, если --target-version не указан?"),
    "poetry": ("V40-P03", "Как имена настроек конфигурации Poetry преобразуются в имена переменных окружения?"),
    "textual": ("V40-T04", "Какие аргументы получает метод watch в Textual, если объявлен один позиционный аргумент или два?"),
    "vite": ("V40-V02", "Что имеет приоритет, если одна переменная окружения Vite определена процессом и в файлах .env?"),
    "eslint": ("V40-E01", "Какие имена файлов ESLint может использовать для плоской конфигурации?"),
}

# Independent source-only case: the Russian request has no export vocabulary,
# while the explicit English translation can find the four original windows.
# Neither source text nor these literal facts are derived from retrieval output.
EXPORT_QUESTION_RU = (
    "Как устроен согласованный и возобновляемый экспорт NacreRelay? "
    "Объясните, какие данные он включает, как продолжить скачивание и чем "
    "ограничен срок доступа, в том числе после отзыва разрешения."
)
EXPORT_QUESTION_EN = (
    "How does a consistent and resumable NacreRelay export work? Explain "
    "which data it includes, how to resume a download, and what limits the "
    "period of access, including after permission revocation."
)
EXPORT_WITNESSES = (
    "An export reads the committed manifest that was current when the export request was accepted. Later commits are not added to that export. Uncommitted import chunks are never included.",
    "Creating an export requires an active session ticket and read permission for the requested workspace. The export does not grant permission to read any other workspace.",
    "An export object is retained for six hours. Each signed download link is valid for twelve minutes. Download permission is checked again on every request, so revocation blocks a download immediately even when the object and link have not expired.",
    "Resume with the same export identifier and a byte Range request. The returned snapshot identifier must match the original response. An expired signed link can be replaced only after a fresh authorization check; replacing the link does not refresh the six-hour object retention period.",
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dataset(args):
    base = args.repo / "eval/prepared_model_comparison40"
    cases = json.loads((base / "questions.json").read_text())["cases"]
    families = json.loads((base / "source_plan.json").read_text())["families"]
    return base, {c["id"]: c for c in cases}, {f["id"]: f for f in families}


def worker(args):
    import yaml
    from docmancer.mcp._docs_server_part01 import _run_async
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime = load("language_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load("language_state", args.repo / "eval/prepared_model_comparison40/run.py")
    corpus, _, families = dataset(args)
    root = args.work / args.group / "project"
    out = args.out / args.group
    if args.group == "controls":
        docs = {"README.md": "# Aster\n\nAster listens on port 8127.\n",
                "packages/auth/README.md": "# Вход\n\nМодуль auth использует порт 9201.\n",
                "packages/other/README.md": "# Andere\n\nPort 9401.\n"}
    elif args.group == "translation-only":
        docs = {
            "README.md": "# NacreRelay\n\nNacreRelay publishes workspace API documentation.\n",
            "docs/exports.md": (args.repo / "eval/fixtures/translation_only_exports/docs/exports.md").read_text(encoding="utf-8"),
        }
    else:
        docs = {p: (corpus / "sources" / args.group / p).read_text(encoding="utf-8")
                for p in families[args.group]["paths"]}
    runtime.write_project(root, docs)
    catalog_file = root / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_file.read_text())
    catalog["documentation_languages"] = {p: ["en"] for p in docs}
    if args.group == "controls":
        for row in catalog["documents"]:
            if row["path"].startswith("packages/"):
                row.update(scope="module", module_path=str(Path(row["path"]).parent))
        catalog["documentation_languages"] = {"README.md": ["en"], "packages/auth/README.md": ["ru"]}
    catalog_file.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    with runtime.isolated_service(args.work / args.group / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        if args.group == "controls":
            # Real local registry fixture setup; no remote fetch or fake status handler.
            from docmancer.docs.registry import LibraryRegistry
            now = datetime.now(timezone.utc).isoformat()
            record = LibraryRegistry(config.index.db_path).upsert(
                library="aster-language", ecosystem="pypi", version="1.0.0",
                docs_url="https://example.invalid/aster/1.0.0", source_type="api", now=now,
                last_refreshed_at=now, status="ready", target_spec={
                    "active_manifest_digest": "a" * 64,
                    # Real registry refresh state: proposed French metadata
                    # must not replace the active German snapshot's declaration.
                    "source_manifest": {"documentation_languages": ["fr"], "digest": "b" * 64},
                    "active_source_manifest": {"documentation_languages": ["de"], "digest": "a" * 64},
                })
            save(out / "library.json", {"canonical_id": record.canonical_id})
        before_db, before_files = helper.logical_state(inventory), helper.source_state(root)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="off" if args.group in {"controls", "translation-only"} else "minilm-sections-v1",
                          DOCATLAS_MINILM_MODEL_DIR=str(args.model), DOCATLAS_CONTEXT_ABSTENTION="off",
                          DOCATLAS_MCP_TEXT_FALLBACK="1", HF_HUB_OFFLINE="1")
        with observe_section_compression() as receipts:
            try:
                asyncio.run(_run_async(service))
            finally:
                peak = Path("/sys/fs/cgroup/memory.peak")
                save(out / "server.json", {"observations": receipts,
                    "files_unchanged": helper.source_state(root) == before_files,
                    "database_unchanged": helper.logical_state(inventory) == before_db,
                    "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                    "container_peak_bytes": int(peak.read_text()) if peak.exists() else None})


async def client(args):
    import yaml
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections
    _, cases, _ = dataset(args)
    results, calls = [], 0
    groups = ["controls"] if args.controls_only else [*PAIRS, "controls", "translation-only"]
    for group in groups:
        out = args.out / group
        out.mkdir(parents=True)
        root = args.work / group / "project"
        params = StdioServerParameters(command=sys.executable, args=["-I", str(Path(__file__).resolve()),
            "--worker", "--group", group, "--repo", str(args.repo), "--work", str(args.work),
            "--out", str(args.out), "--model", str(args.model)], env=dict(os.environ))
        with (out / "stderr.log").open("w") as err:
          async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                await session.initialize()
                tools = {t.name: t for t in (await session.list_tools()).tools}
                assert set(tools) == {"get_docs_context", "prepare_docs", "docs_status"}
                assert "include_language" in tools["docs_status"].inputSchema["properties"]
                assert "search_question" in tools["get_docs_context"].inputSchema["properties"]
                async def call(label, tool, request, error=None):
                    nonlocal calls
                    reply = await session.call_tool(tool, request)
                    calls += 1
                    assert len(reply.content) == 1 and reply.content[0].type == "text"
                    wire = reply.content[0].text
                    (out / f"{label}-wire.json").write_text(wire, encoding="utf-8")
                    raw = json.loads(wire)
                    if error:
                        assert reply.isError and (raw.get("error") or {}).get("reason_code") == error, raw
                    else:
                        assert not reply.isError, raw
                    return expand_sections(raw)
                status_req = {"action": "project", "project_path": str(root), "details": False}
                if group in PAIRS:
                    status = await call("language", "docs_status", {**status_req, "include_language": True})
                    assert status["documentation_language"]["languages"] == ["en"]
                    assert status["documentation_language"]["basis"] == "catalog_declaration"
                    case_id, ru = PAIRS[group]
                    en = cases[case_id]["question"]
                    request = {"project_path": str(root), "scope": "project"}
                    a = await call("english", "get_docs_context", {**request, "question": en})
                    b = await call("russian-original", "get_docs_context", {**request, "question": ru})
                    c = await call("translated", "get_docs_context", {**request, "question": ru, "search_question": en})
                    from collections import Counter
                    signature = lambda payload: Counter((r["path_or_url"], r["line_start"], r["line_end"], r["snippet"]) for r in payload["sources"])
                    paired_equal = signature(a) == signature(c)  # acquisition union may change extra sections
                    for name, payload in (("english", a), ("russian-original", b), ("translated", c)):
                        save(out / f"{name}-expanded.json", payload)
                    results.append({"group": group, "case_id": case_id, "paired_source_content_equality": paired_equal,
                                    "english_question": en, "original_question": ru})
                elif group == "translation-only":
                    language = await call("exports-language", "docs_status", {
                        "action": "project", "project_path": str(root), "include_language": True})
                    assert language["documentation_language"]["languages"] == ["en"]
                    assert language["documentation_language"]["source_count"] == 2
                    request = {"project_path": str(root), "scope": "project", "question": EXPORT_QUESTION_RU,
                               "search_question": EXPORT_QUESTION_EN, "lookup_queries": []}
                    payload = await call("exports-translation-only", "get_docs_context", request)
                    save(out / "exports-expanded.json", payload)
                    original = (args.repo / "eval/fixtures/translation_only_exports/docs/exports.md").read_bytes()
                    live = (root / "docs/exports.md").read_bytes()
                    assert live == original, "prepared source must match the independent fixture"
                    lines = original.decode("utf-8").splitlines(keepends=True)
                    exported = []
                    for row in payload.get("sources", []):
                        if row["path_or_url"] != "docs/exports.md":
                            continue
                        assert row["scope"] == "project" and row["authority"] == "source_of_truth"
                        assert row["project_identity"] == "local:" + sha(str(root).encode())
                        assert row["version_binding"] == "unversioned"
                        assert 1 <= row["line_start"] <= row["line_end"] <= len(lines)
                        assert row["snippet"] in "".join(lines[row["line_start"] - 1:row["line_end"]])
                        exported.append(row["snippet"])
                    missing = [fact for fact in EXPORT_WITNESSES if not any(fact in text for text in exported)]
                    assert not missing, {"missing_required_export_facts": missing,
                                         "source_paths": [row["path_or_url"] for row in payload.get("sources", [])]}
                    restricted = await call("exports-wrong-scope", "get_docs_context", {
                        **request, "scope": "module", "module_path": "packages/other"})
                    assert not any(row["path_or_url"] == "docs/exports.md"
                                   for row in restricted.get("sources", [])), "translated lookup escaped module scope"
                    await call("exports-no-patch", "get_docs_context", {
                        **request, "context_format": "patch_context"}, "search_question_docs_only")
                    results.append({"group": group, "covered": len(EXPORT_WITNESSES),
                                    "required": len(EXPORT_WITNESSES), "source_sha256": sha(original),
                                    "wrong_scope_excluded": True, "patch_context_rejected": True})
                else:
                    base = await call("legacy", "docs_status", status_req)
                    assert "documentation_language" not in base
                    project = await call("project", "docs_status", {**status_req, "include_language": True})
                    default_project = await call("project-default", "docs_status", {
                        "action": "project", "project_path": str(root), "include_language": True})
                    assert default_project == project, "omitted details must use language-only preflight"
                    assert project["project"] == {"project_path": str(root)}
                    detailed_base = await call("legacy-detailed", "docs_status", {**status_req, "details": True})
                    detailed = await call("project-detailed", "docs_status", {
                        **status_req, "include_language": True, "details": True})
                    assert detailed == {**detailed_base, "documentation_language": project["documentation_language"]}
                    assert set(base["project"]) > {"project_path"}, "normal status must retain diagnostics"
                    assert await call("legacy-after-preflight", "docs_status", status_req) == base
                    assert project["documentation_language"]["languages"] == ["en"]
                    assert project["documentation_language"]["source_count"] == 1
                    auth = await call("module", "docs_status", {**status_req, "include_language": True, "module": "packages/auth"})
                    assert auth["documentation_language"]["languages"] == ["ru"]
                    assert auth["documentation_language"]["scope"] == "module"
                    unknown = await call("unknown-module", "docs_status", {**status_req, "include_language": True, "module": "packages/other"})
                    assert unknown["documentation_language"]["status"] == "unknown"
                    alias = await call("module-alias", "docs_status", {**status_req, "include_language": True, "module": "auth"})
                    assert alias["documentation_language"]["status"] == "unknown"
                    await call("invalid-action", "docs_status", {"action": "jobs", "include_language": True}, "language_status_action_required")
                    lib = json.loads((out / "library.json").read_text())["canonical_id"]
                    library = await call("library", "docs_status", {"action": "library", "canonical_id": lib, "include_language": True})
                    assert library["library"] == {"canonical_id": lib}
                    library_base = await call("library-legacy", "docs_status", {"action": "library", "canonical_id": lib})
                    library_full = await call("library-detailed", "docs_status", {
                        "action": "library", "canonical_id": lib, "include_language": True, "details": True})
                    assert library_full == {**library_base, "documentation_language": library["documentation_language"]}
                    assert library["documentation_language"]["languages"] == ["de"], library
                    missing = await call("missing-library", "docs_status", {"action": "library", "canonical_id": lib + "-missing", "include_language": True})
                    assert missing["documentation_language"]["status"] == "unknown"
                    path = root / "docatlas.project-docs.yaml"
                    original = path.read_bytes()
                    try:
                        catalog = yaml.safe_load(original)
                        catalog["documentation_languages"]["README.md"] = ["en", "ru"]
                        path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
                        mixed = await call("mixed", "docs_status", {**status_req, "include_language": True})
                        assert mixed["documentation_language"]["status"] == "mixed"
                        assert mixed["documentation_language"]["snapshot_sha256"] != project["documentation_language"]["snapshot_sha256"]
                        catalog["documentation_languages"] = {}
                        path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
                        unknown = await call("no-declarations", "docs_status", {**status_req, "include_language": True})
                        assert unknown["documentation_language"]["status"] == "unknown"
                        catalog["documentation_languages"] = {"../../not-a-member": ["en"]}
                        path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
                        invalid = await call("invalid-declaration", "docs_status", {**status_req, "include_language": True})
                        assert invalid["documentation_language"]["status"] == "unknown"
                        assert not invalid["documentation_language"]["languages"]
                    finally:
                        path.write_bytes(original)
                    req = {"project_path": str(root), "scope": "project", "question": "Какой порт использует Aster?"}
                    await call("too-many-lookups", "get_docs_context", {**req, "search_question": "What port does Aster use?", "lookup_queries": [f"Aster port {i}" for i in range(5)]}, "search_question_lookup_limit")
                    await call("blank-translation", "get_docs_context", {**req, "search_question": "  "}, "invalid_search_question")
                    ok = await call("translated-source", "get_docs_context", {**req, "search_question": "What port does Aster use?"})
                    assert any("8127" in r["snippet"] for r in ok["sources"])
                    assert ok["sources"]
                    for row in ok["sources"]:
                        assert row["path_or_url"] == "README.md", "module source escaped project scope"
                        assert row["scope"] == "project"
                        assert row["version_binding"] == "unversioned"
                        assert row["authority"] == "source_of_truth"
                        assert row["project_identity"] == "local:" + sha(str(root).encode())
                        source = (root / "README.md").read_bytes()
                        # content_sha256 is a projection fingerprint, not the raw file hash.
                        assert len(row["content_sha256"].removeprefix("sha256:")) == 64
                        lines = source.decode().splitlines(keepends=True)
                        assert row["snippet"] in "".join(lines[row["line_start"] - 1:row["line_end"]])
                    results.append({"group": "controls", "passed": True})
        state = json.loads((out / "server.json").read_text())
        assert state["files_unchanged"] and state["database_unchanged"], state
        if group in PAIRS:
            en = cases[PAIRS[group][0]]["question"]
            assert state["observations"][-1]["scoring_question_sha256"] == sha(en.encode())
    save(args.out / "DELIVERY.json", {"public_calls": calls, "preparations": len(groups), "results": results})
    return results, calls


def assess(args, results, calls):
    corpus, cases, families = dataset(args)
    oracle = load("language_oracle", corpus / "evaluate.py")
    gold = {c["id"]: c for c in json.loads((corpus / "gold_spans.json").read_text())["cases"]}
    coverage = []
    for row in results:
        if row["group"] in {"controls", "translation-only"}:
            continue
        family, case_id = row["group"], row["case_id"]
        prepared = {"root": str(args.work / family / "project"), "sources": {}}
        for path in families[family]["paths"]:
            data = (corpus / "sources" / family / path).read_bytes()
            text, offsets = data.decode(), [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared["sources"][path] = {"raw": data, "content": text, "sha256": sha(data), "line_offsets": offsets, "errors": []}
        for arm in ("english", "russian-original", "translated"):
            payload = json.loads((args.out / family / f"{arm}-expanded.json").read_text())
            _, intervals, errors = oracle._source_rows(payload, prepared)
            value = oracle._gold(cases[case_id], gold[case_id], prepared, intervals)
            assert not errors and not value.get("errors"), (family, arm, errors, value)
            passed = bool(value["all_documented_claims_covered"])
            coverage.append({"case_id": case_id, "arm": arm, "complete": passed})
            if arm != "russian-original":
                assert passed, (family, arm, value)
    save(args.out / "SUMMARY.json", {"sha": os.environ.get("TESTED_SHA"), "passed": True,
        "public_calls": calls, "preparations": len(results), "coverage": coverage,
        "new_tool_count": 0, "language_detector_used": False,
        "boundary": "installed wheel; real SQLite; actual public MCP client; declared metadata, not automatic detection",
        "no_claim_of_llm_answer_correctness": True})


def main():
    parser = argparse.ArgumentParser()
    for flag in ("repo", "work", "out", "model"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--group", choices=[*PAIRS, "controls", "translation-only"])
    parser.add_argument("--controls-only", action="store_true")
    args = parser.parse_args()
    for key in ("repo", "work", "out", "model"):
        setattr(args, key, getattr(args, key).resolve())
    if args.worker:
        worker(args)
        return
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo), "installed package required"
    assert all(p.read_bytes() == (args.repo / "docmancer" / p.relative_to(origin)).read_bytes() for p in origin.rglob("*.py"))
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    corpus, _, _ = dataset(args)
    frozen = {str(p.relative_to(args.repo)): sha(p.read_bytes()) for p in corpus.rglob("*") if p.is_file()}
    save(args.out / "FREEZE.json", {"sha": os.environ.get("TESTED_SHA"), "inputs": frozen, "pairs": PAIRS})
    results, calls = asyncio.run(client(args))
    assess(args, results, calls)
    assert all(sha((args.repo / p).read_bytes()) == digest for p, digest in frozen.items())


if __name__ == "__main__":
    main()
