"""Create an explicit OpenCode V2 read-only documentation location.

No server/model calls, source indexing, existing configuration edits or skill
installation. Both comparison backends share instructions and host output guards.
Use an installed DocAtlas interpreter, including for the adapter's offline counter.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys

PROFILE = "documentation-light-v1"
HERE = Path(__file__).resolve().parent


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_control_snapshot(root: Path) -> list[dict[str, str]]:
    """Admit only an already isolated, finite docs-only comparison corpus.

    A whole repository is not equivalent to project-scoped MCP retrieval. This
    control never exports or guesses a subset of a larger/private repository.
    Public preparation must separately establish the MCP active snapshot.
    """
    from docmancer.docs.project_docs_catalog import CATALOG_FILENAME, read_project_docs_catalog

    catalog = read_project_docs_catalog(root)
    if (not catalog.present or not catalog.valid or catalog.roots or catalog.code_files or not catalog.entries or
            any(entry.scope != "project" or entry.module_path or entry.status != "active" or
                entry.authority not in {"source_of_truth", "supporting"} for entry in catalog.entries)):
        raise ValueError("files control requires an isolated finite active project-only docs catalog")
    expected = {entry.path for entry in catalog.entries} | {CATALOG_FILENAME}
    if (root / "AGENTS.md").is_file():
        expected.add("AGENTS.md")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("files control does not admit source symlinks")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise ValueError("files control requires regular files and directories")
    if actual != expected:
        raise ValueError("files control requires exactly the catalog documents, catalog and optional root AGENTS.md")
    return [{"path": relative, "sha256": _digest((root / relative).read_bytes())} for relative in sorted(actual)]


def build_profile(*, project_root: Path, workspace: Path, backend: str,
                  executable: Path, python: Path, server_environment: dict[str, str] | None = None,
                  server_name: str = "docatlas", agent_name: str = "docs",
                  model: str | None = None, frozen: bool = False,
                  max_steps: int | None = None) -> tuple[dict, dict]:
    """Build a new configuration, without changing the selected retrieval policy.

    This first profile binds project scope. Module/library/all-scope workflows use
    the ordinary integration until a separately explicit profile supports them.
    Language metadata is not synthesized or cached by this builder.
    """
    from docmancer.mcp.project_binding import make_binding

    if backend not in {"mcp", "files"}:
        raise ValueError("backend must be mcp or files")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", server_name):
        raise ValueError("server_name must be an explicit stable MCP prefix")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", agent_name):
        raise ValueError("invalid agent_name")
    if max_steps is not None and (type(max_steps) is not int or max_steps <= 0):
        raise ValueError("max_steps must be a positive integer or omitted")
    if not project_root.is_absolute() or not workspace.is_absolute():
        raise ValueError("project and workspace must be explicit absolute paths")
    root, location = project_root.resolve(strict=True), workspace.resolve(strict=True)
    if not root.is_dir() or not location.is_dir():
        raise ValueError("project and workspace must be existing directories")
    if backend == "files" and (location.is_relative_to(root) or root.is_relative_to(location)):
        raise ValueError("files control requires a separate location outside and not containing the frozen corpus")
    # Preserve venv executable paths: resolving their symlink can select the
    # system interpreter instead of the installed isolated candidate.
    for command in (executable, python):
        if not command.is_absolute() or not command.is_file() or not os.access(command, os.X_OK):
            raise ValueError("executable and python must be absolute installed executable paths")
    env = dict(server_environment or {})
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in env.items()):
        raise ValueError("server_environment must map strings to strings")
    if env.get("DOCATLAS_MCP_MODEL_VIEW") not in (None, "", "off"):
        raise ValueError("The text documentation profile cannot use a private-ledger model view")
    env.update(DOCATLAS_PROJECT_BINDING=json.dumps(make_binding(root, location)),
               DOCATLAS_MCP_TEXT_FALLBACK="1", DOCATLAS_MCP_COMPACT_TEXT="1",
               DOCATLAS_CONTEXT_PRESENTATION="literal-v2",
               DOCATLAS_MCP_ADMIN_TOOLS="0", DOCATLAS_MCP_ADVANCED_TOOLS="0",
               DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0")
    common = (HERE / "profile/common.txt").read_text(encoding="utf-8").strip()
    specific = (HERE / f"profile/{backend}.txt").read_text(encoding="utf-8").strip()
    binding = f"Bound documentation project: {json.dumps(str(root), ensure_ascii=False)}. Scope: project."
    if frozen:
        binding += " This comparison uses a designated frozen source corpus; do not read evaluation annotations."
    system = "\n\n".join((common, binding, specific))
    file_snapshot = _file_control_snapshot(root) if backend == "files" else None
    names = ([f"{server_name}_get_docs_context", f"{server_name}_docs_status",
              f"{server_name}_read_docs_source", "opencode_read_mcp_resource"]
             if backend == "mcp" else ["read", "glob", "grep"])
    permissions = [{"action": "*", "resource": "*", "effect": "deny"}]
    for name in names:
        # OpenCode uses relative read resources inside a worktree and absolute
        # ones outside. The mandatory profile plugin enforces canonical paths
        # and the exact frozen corpus for all three native file tools.
        resource = f"{server_name}:docatlas://source/*" if name == "opencode_read_mcp_resource" else "*"
        permissions.append({"action": name, "resource": resource, "effect": "allow"})
    if backend == "files":
        permissions.append({"action": "external_directory", "resource": str(root) + "/*", "effect": "allow"})
    agent = {"mode": "primary", "description": "Read existing project documentation without changes",
             "system": system, "permissions": permissions}
    if model:
        agent["model"] = model
    if max_steps is not None:
        agent["steps"] = max_steps
    profile_options = {"backend": backend, "projectRoot": str(root), "serverName": server_name}
    if file_snapshot is not None:
        profile_options["fileSnapshot"] = file_snapshot
    config = {"$schema": "https://opencode.ai/config.json", "default_agent": agent_name,
              "snapshots": False, "agents": {agent_name: agent},
              "plugins": [{"package": str(HERE / "profile"), "options": profile_options},
                  {"package": str(HERE), "options": {"python": str(python),
                      "tools": names[:-1] if backend == "mcp" else [],
                      "guard_tools": ["opencode_read_mcp_resource"] if backend == "mcp" else names}}],
              "tool_output": {"max_bytes": 6400000, "max_lines": 6400000}}
    if backend == "mcp":
        config["mcp"] = {"servers": {server_name: {
            "type": "local", "command": [str(executable), "mcp", "docs-serve"],
            "cwd": str(root), "environment": env, "codemode": False}}}
    # A separate location must not accidentally drop the bound project's root
    # instructions. Normal OpenCode instruction discovery remains enabled too.
    instructions = root / "AGENTS.md"
    if not location.is_relative_to(root) and instructions.is_file():
        config["instructions"] = [str(instructions)]
    receipt = {"profile": PROFILE, "backend": backend, "project_path": str(root),
               "workspace_path": str(location), "scope": "project", "agent": agent_name,
               "model_step_limit": max_steps,
               "presentation": "literal-v2" if backend == "mcp" else "native-file-text",
               "common_prompt_sha256": _digest(common.encode()), "system_sha256": _digest(system.encode()),
               "allowed_tools": names, "language_preflight": "unchanged; bound language unknown",
               "adapter_execute_tools": names[:-1] if backend == "mcp" else [],
               "adapter_guard_tools": ["opencode_read_mcp_resource"] if backend == "mcp" else names,
               "retrieval_policy_selected_by_profile": False,
               "instructions_disabled": False, "history_pruned": False,
               "file_control_snapshot": file_snapshot,
               "mcp_active_snapshot_verified_by_builder": False,
               "model_calls": 0, "preparation_calls": 0,
               "inputs": {str(path.relative_to(HERE)): _digest(path.read_bytes()) for path in
                          [HERE / "documentation_profile.py", HERE / "profile/common.txt",
                           HERE / f"profile/{backend}.txt", HERE / "profile/index.js", HERE / "index.js",
                           HERE / "count_tokens.py"]},
               "boundary": "Configuration only; actual client/runtime acceptance is recorded separately."}
    return deepcopy(config), receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="Known absolute documentation project root")
    parser.add_argument("--output", type=Path, required=True, help="New dedicated OpenCode location")
    parser.add_argument("--backend", choices=("mcp", "files"), default="mcp")
    parser.add_argument("--executable", type=Path, required=True, help="Absolute installed doc-atlas executable")
    parser.add_argument("--python", type=Path, required=True, help="Absolute interpreter from the same installed environment")
    parser.add_argument("--server-env-json", type=Path, help="Explicit existing server environment map; no policy is selected automatically")
    parser.add_argument("--server-name", default="docatlas")
    parser.add_argument("--agent-name", default="docs")
    parser.add_argument("--model", help="Optional provider/model[#variant]; otherwise use the client's configured model")
    parser.add_argument("--max-steps", type=int, help="Optional explicit host limit; no default model-step cap")
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error("--output must be absolute")
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ("opencode.json", "opencode.jsonc", "profile-receipt.json")):
        parser.error("Refusing to overwrite an existing configuration; select a new dedicated location")
    try:
        environment = json.loads(args.server_env_json.read_text()) if args.server_env_json else None
        config, receipt = build_profile(project_root=args.project, workspace=args.output,
            backend=args.backend, executable=args.executable, python=args.python,
            server_environment=environment, server_name=args.server_name, agent_name=args.agent_name, model=args.model,
            max_steps=args.max_steps)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    for name, value in (("opencode.json", config), ("profile-receipt.json", receipt)):
        with (args.output / name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"profile": PROFILE, "location": str(args.output), "agent": args.agent_name,
                      "next": "Run OpenCode here with this agent; pass the unchanged question through stdin."}))


if __name__ == "__main__":
    main()
