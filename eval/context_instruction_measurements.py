"""Measure installed instruction surfaces without provider or answering-model calls.

The paired mode runs this driver against two installed wheels with the same
dependencies. Each wheel installs global/project guidance in an isolated home
and advertises its tools through the registered, real MCP stdio command.
Historical source-only baselines remain supported, but are labelled separately.
Surfaces overlap and are never summed into an invented default host cost.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

NAMES = ("get_docs_context", "prepare_docs", "docs_status")
HISTORICAL_BASELINE = "bde2a101032b204e6a4168c0e8a63f45040b3ddc"
SURFACE_NOTES = {
    "root_skill": "Repository source; not an additional default OpenCode instruction.",
    "installed_bootstrap_template": "Template source; overlaps with rendered installed guidance.",
    "installed_global_skill": "Complete installed SKILL.md; skill expansion is optional.",
    "installed_global_skill_frontmatter": "Subset of installed_global_skill, not additive.",
    "installed_global_skill_body": "Subset of installed_global_skill, not additive.",
    "installed_project_bootstrap": "Complete AGENTS.md from explicit project installation.",
    "public_tools_text_host": "Canonical actual tools/list tool array; host framing is not counted.",
    "optional_reference": "Installed reference read on demand; excluded from default context totals.",
}
VERIFIED_FILES = (
    "mcp/agent_config.py", "mcp/_docs_server_shared.py", "mcp/_docs_server_tool_data.py",
    "mcp/_docs_server_part01.py", "docs/application/standalone_text_view.py",
    "docs/interfaces/mcp/error_contract.py", "docs/agent_contract.py",
    "mcp/agent_workflow_contract.py", "cli/_commands_part01.py", "cli/_commands_part02.py",
    "cli/_commands_part05.py", "templates/agent_contract.md", "templates/skill.md",
    "templates/project_bootstrap.md",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def baseline_tools(source):
    """Read historical literal declarations without importing baseline code."""
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in ("PUBLIC_ADVERTISED_DESCRIPTIONS", "PUBLIC_ADVERTISED_INPUT_SCHEMAS"):
                values[node.target.id] = ast.literal_eval(node.value)
    return [{"name": name, "description": values["PUBLIC_ADVERTISED_DESCRIPTIONS"][name],
             "inputSchema": values["PUBLIC_ADVERTISED_INPUT_SCHEMAS"][name]} for name in NAMES]


def validation(value):
    if isinstance(value, dict):
        return {k: validation(v) for k, v in value.items() if k != "description"}
    if isinstance(value, list):
        return [validation(v) for v in value]
    return value


def frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            boundary = end + len("\n---\n")
            return text[:boundary], text[boundary:]
    return "", text


async def tools_list(entry, env, cwd, stderr_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = entry["command"]
    assert isinstance(command, list) and command
    params = StdioServerParameters(command=command[0], args=command[1:],
                                  env={**env, **entry["environment"]}, cwd=str(cwd))
    with stderr_path.open("w", encoding="utf-8") as stderr:
        async with stdio_client(params, errlog=stderr) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=60)) as session:
                await session.initialize()
                result = await session.list_tools()
                assert not result.nextCursor, "one tools/list page must contain the default public surface"
                envelope = result.model_dump(mode="json", by_alias=True, exclude_none=True)
                catalog = envelope["tools"]
                assert tuple(tool["name"] for tool in catalog) == NAMES
                assert all("outputSchema" not in tool for tool in catalog), "text host must not advertise outputSchema"
                return catalog, envelope


def probe(repo, out, source_ref):
    """Called in a subprocess with that wheel's own interpreter and CLI."""
    import docmancer

    installed = Path(docmancer.__file__).resolve().parent
    assert installed.is_relative_to(Path(sys.prefix).resolve()), (installed, sys.prefix)
    assert not installed.is_relative_to(repo), "measurement imported the checkout instead of the wheel"
    source_hashes = {}
    for relative in VERIFIED_FILES:
        actual = (installed / relative).read_bytes()
        assert actual == (repo / "docmancer" / relative).read_bytes(), relative
        source_hashes[relative] = hashlib.sha256(actual).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="docatlas-instruction-probe-") as temporary:
        root = Path(temporary)
        home, project = root / "home", root / "project"
        home.mkdir(mode=0o700)
        project.mkdir(mode=0o700)
        env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
        env.update(PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
                   HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   XDG_DATA_HOME=str(home / ".local/share"), XDG_CACHE_HOME=str(home / ".cache"),
                   DOCATLAS_HOME=str(home / ".docatlas"), DOCATLAS_OFFLINE="1",
                   DOCATLAS_AUTO_VECTORS="0", HF_HUB_OFFLINE="1", NO_PROXY="*",
                   PYTHONNOUSERSITE="1")
        for label, extra in (("global", []), ("project", ["--project"])):
            completed = subprocess.run(
                [sys.executable, "-I", "-m", "docmancer.cli", "install", "opencode", *extra],
                cwd=project, env=env, capture_output=True, text=True, timeout=60,
            )
            (out.parent / f"{label}-install.log").write_text(
                completed.stdout + completed.stderr, encoding="utf-8")
            assert completed.returncode == 0, (label, completed.stdout, completed.stderr)
        skill_path = home / ".config/opencode/skills/docatlas/SKILL.md"
        bootstrap_path = project / "AGENTS.md"
        skill = skill_path.read_text(encoding="utf-8")
        skill_frontmatter, skill_body = frontmatter(skill)
        assert skill_frontmatter and "{{" not in skill
        bootstrap = bootstrap_path.read_text(encoding="utf-8")
        assert bootstrap and "{{" not in bootstrap
        registrations = []
        for path in (home / ".config/opencode/opencode.json", project / "opencode.json"):
            config = json.loads(path.read_text(encoding="utf-8"))
            entries = list(config["mcp"]["servers"].values())
            assert len(entries) == 1
            entry = entries[0]
            assert entry["environment"]["DOCATLAS_MCP_TEXT_FALLBACK"] == "1"
            assert entry["environment"]["DOCATLAS_MCP_COMPACT_TEXT"] == "1"
            assert entry["environment"].get("DOCATLAS_MCP_MODEL_VIEW") != "1"
            registrations.append(entry)
        assert registrations[0] == registrations[1], "fresh global/project installs must select the same transport"
        catalog, envelope = asyncio.run(tools_list(
            registrations[0], env, project, out.parent / "tools-list.stderr.log"))
        surfaces = {
            "root_skill": (repo / "SKILL.md").read_text(encoding="utf-8"),
            "installed_bootstrap_template": (installed / "templates/agent_contract.md").read_text(encoding="utf-8"),
            "installed_global_skill": skill,
            "installed_global_skill_frontmatter": skill_frontmatter,
            "installed_global_skill_body": skill_body,
            "installed_project_bootstrap": bootstrap,
            "public_tools_text_host": canonical(catalog),
        }
        reference_sets = {}
        for label, path in (("global", skill_path), ("project", bootstrap_path)):
            links = re.findall(r"\]\((docatlas-references/[^)]+\.md)\)", path.read_text(encoding="utf-8"))
            references = {}
            for link in sorted(set(links)):
                target = (path.parent / link).resolve()
                assert target.is_relative_to(path.parent.resolve()), link
                references[link] = target.read_text(encoding="utf-8")
                surfaces[f"optional_reference/{label}/{Path(link).name}"] = references[link]
            reference_sets[label] = {name: sha(text) for name, text in references.items()}
        save(out, {
            "source_ref": source_ref, "boundary": "actual installed CLI and registered MCP stdio tools/list",
            "python": sys.executable, "prefix": sys.prefix, "package_origin": str(installed),
            "installed_source_sha256": source_hashes, "registration": registrations[0],
            "catalog": catalog, "tools_list_envelope": envelope, "surfaces": surfaces,
            "reference_sha256": reference_sets,
            "operations": {"cli_installs": 2, "mcp_sessions": 1, "tools_list_calls": 1, "tool_calls": 0},
        })


def run_probe(python, repo, source_ref, out):
    completed = subprocess.run(
        [str(python), "-I", str(Path(__file__).resolve()), "--probe", "--repo", str(repo),
         "--source-ref", source_ref, "--out", str(out)],
        capture_output=True, text=True, timeout=240,
    )
    (out.parent / "driver.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    assert completed.returncode == 0, (source_ref, completed.stdout, completed.stderr)
    return json.loads(out.read_text(encoding="utf-8"))


def source_baseline(directory, source_ref):
    catalog = baseline_tools((directory / "tools.py").read_text(encoding="utf-8"))
    return {
        "source_ref": source_ref, "boundary": "historical static declarations, not an installed baseline",
        "catalog": catalog,
        "surfaces": {
            "root_skill": (directory / "SKILL.md").read_text(encoding="utf-8"),
            "installed_bootstrap_template": (directory / "agent_contract.md").read_text(encoding="utf-8"),
            "public_tools_text_host": canonical(catalog),
        },
    }


def compare(before, after, out):
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    assert tuple(tool["name"] for tool in before["catalog"]) == NAMES
    assert [validation(t["inputSchema"]) for t in before["catalog"]] == [
        validation(t["inputSchema"]) for t in after["catalog"]], "input validation drifted"
    def amount(text):
        if text is None:
            return None
        raw = text.encode("utf-8")
        return {"bytes": len(raw), "o200k_tokens": projection_token_count(raw), "sha256": sha(text)}
    def pair(old, new):
        left, right = amount(old), amount(new)
        return {"before": left, "after": right,
                "saved_bytes": left["bytes"] - right["bytes"] if left and right else None,
                "saved_tokens": left["o200k_tokens"] - right["o200k_tokens"] if left and right else None,
                "saved_percent": round(100 * (1 - right["o200k_tokens"] / left["o200k_tokens"]), 2)
                if left and right and left["o200k_tokens"] else None}
    surfaces = {}
    for name in sorted(set(before["surfaces"]) | set(after["surfaces"])):
        note_key = "optional_reference" if name.startswith("optional_reference/") else name
        surfaces[name] = {"meaning": SURFACE_NOTES[note_key], **pair(
            before["surfaces"].get(name), after["surfaces"].get(name))}
    attribution = {}
    for old, new in zip(before["catalog"], after["catalog"], strict=True):
        assert old["name"] == new["name"]
        attribution[new["name"]] = {
            "complete_tool": pair(canonical(old), canonical(new)),
            "description": pair(old.get("description", ""), new.get("description", "")),
            "input_schema": pair(canonical(old["inputSchema"]), canonical(new["inputSchema"])),
        }
    result = {
        "baseline": before["source_ref"], "candidate": after["source_ref"],
        "baseline_boundary": before["boundary"], "candidate_boundary": after["boundary"],
        "codec": "o200k_base; bundled hash-checked vocabulary from tiktoken 0.11.0",
        "schema_validation_equal": True, "surfaces": surfaces, "tool_attribution": attribution,
        "accounting": {
            "default_total": None,
            "reason": "Do not sum overlapping root/template/installed/frontmatter/schema surfaces. Optional skill/reference loading and provider framing were not observed.",
            "provider_usage": None, "paid_calls": 0, "autonomous_opencode_session": "NOT_TESTED",
            "operations": {"baseline": before.get("operations"), "candidate": after.get("operations")},
        },
    }
    save(out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, help="Historical flat source snapshot (fallback mode).")
    parser.add_argument("--baseline-ref", default=HISTORICAL_BASELINE)
    parser.add_argument("--baseline-python", type=Path, help="Separate interpreter with the exact baseline wheel installed.")
    parser.add_argument("--baseline-repo", type=Path, help="Exact baseline source tree used only to verify installed bytes.")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-ref", default=os.environ.get("TESTED_SHA", "unrecorded"))
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.repo, args.out = args.repo.resolve(), args.out.resolve()
    if args.probe:
        probe(args.repo, args.out, args.source_ref)
        return
    if args.baseline_python:
        if not args.baseline_repo or args.baseline:
            parser.error("--baseline-python requires --baseline-repo and excludes --baseline")
        baseline_out = args.out.parent / "baseline" / "PROBE.json"
        baseline_out.parent.mkdir(parents=True, exist_ok=True)
        before = run_probe(args.baseline_python, args.baseline_repo.resolve(), args.baseline_ref, baseline_out)
    else:
        if not args.baseline:
            parser.error("provide --baseline-python/--baseline-repo or --baseline")
        before = source_baseline(args.baseline, args.baseline_ref)
    candidate_out = args.out.parent / "candidate" / "PROBE.json"
    candidate_out.parent.mkdir(parents=True, exist_ok=True)
    after = run_probe(Path(sys.executable), args.repo, args.source_ref, candidate_out)
    compare(before, after, args.out)


if __name__ == "__main__":
    main()
