"""Corrected, one-attempt Meridian live runner; historical Step12 stays immutable.

Run with the installed Qwen environment's Python. `run` can incur answering
provider charges and requires separately authorized real runtime/credentials.
All twelve configurations and their hashed inputs are frozen before session one;
input drift stops the experiment before launching another session.
`classify-history` only reads the twelve saved Step12 CLI trajectories.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
HISTORY = HERE.parent / "step12-live-comparison"
DATA = HERE.parent / "step10-multidoc-gate"
POLICY = HERE.parent / "step10-qwen-validation/provenance/original-policy.json"
MODEL = "openai/gpt-6.1-terra#low"
ARMS = ("qwen-off", "qwen-one-hop", "files")
CASES = ("V-M1", "V-M2", "V-M3", "V-M4")
PROFILE = TREE / "integrations/opencode-v2-compact"
OBSERVER = HISTORY / "observer"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


RUNTIME = module("step13_session_runtime", HERE / "session_runtime.py")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME.save_new(path, value)


def file_identity(path):
    return {"resolved_path": str(path.resolve(strict=True)), "sha256": sha(path)}


def pin_file(inputs, path, expected=None):
    identity = file_identity(path)
    if ((expected is not None and identity["sha256"] != expected) or
            (str(path) in inputs and inputs[str(path)] != identity)):
        raise ValueError("frozen input changed during preflight: " + str(path))
    inputs[str(path)] = identity
    return identity["sha256"]


def input_drift(inputs):
    changed = []
    for name, identity in inputs.items():
        try:
            same = file_identity(Path(name)) == identity
        except OSError:
            same = False
        if not same:
            changed.append(name)
    return changed


@contextmanager
def server_environment(values):
    keys = {key for key in os.environ if key.startswith("DOCATLAS_")} | set(values)
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in tuple(os.environ):
            if key.startswith("DOCATLAS_"):
                del os.environ[key]
        os.environ.update(values)
        yield
    finally:
        for key in tuple(os.environ):
            if key.startswith("DOCATLAS_"):
                del os.environ[key]
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def classify_history(output):
    if not output.is_absolute():
        raise ValueError("output must be a new absolute directory")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for case in CASES:
        for arm in ARMS:
            source = HISTORY / arm / case
            events = [json.loads(line) for line in (source / "raw.jsonl").read_text().splitlines() if line.strip()]
            old_receipt = json.loads((source / "receipt.json").read_text())
            outcome = RUNTIME.classify_session(events, returncode=old_receipt["exit"])
            outcome.pop("answer")
            results.append({"arm": arm, "case": case, "raw_sha256": sha(source / "raw.jsonl"), **outcome})
    failed = [(row["arm"], row["case"]) for row in results if not row["transport_pass"]]
    result = {"boundary": "Offline classification of saved CLI data, not new model/client/lifecycle execution.",
              "sessions_classified": len(results), "new_product_calls": 0, "new_model_calls": 0,
              "expected_failed_case": ["qwen-one-hop", "V-M4"], "results": results,
              "passed": failed == [("qwen-one-hop", "V-M4")] and
                        next(row for row in results if row["arm"] == "qwen-one-hop" and row["case"] == "V-M4")
                        ["retrieval_status"] == "failed"}
    save(output / "classification.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, ensure_ascii=False))
    return 0 if result["passed"] else 1


def verify_runtime(args, inputs):
    import docmancer
    from docmancer.docs.application import context_evidence_scoring as scorer
    import importlib.metadata
    import torch

    root = Path(docmancer.__file__).resolve().parent
    if root.is_relative_to(TREE):
        raise ValueError("live comparison requires an isolated installed wheel, not checkout imports")
    distribution = importlib.metadata.distribution("doc-atlas")
    if Path(distribution.locate_file("docmancer")).resolve() != root or not distribution.files:
        raise ValueError("installed package metadata does not identify the imported product")
    product, metadata = {}, {}
    for entry in sorted(distribution.files, key=str):
        if "__pycache__" in entry.parts or entry.suffix == ".pyc":
            continue  # Interpreter-generated caches are not wheel source inputs.
        installed = Path(distribution.locate_file(entry))
        if entry.parts[0] == "docmancer":
            if entry.is_absolute() or ".." in entry.parts:
                raise ValueError("invalid packaged product path")
            digest = pin_file(inputs, TREE / entry)
            pin_file(inputs, installed, digest)
            record = entry.hash
            if (record is None or record.mode != "sha256" or record.value !=
                    base64.urlsafe_b64encode(bytes.fromhex(digest)).decode().rstrip("=")):
                raise ValueError("installed product disagrees with wheel RECORD: " + str(entry))
            product[str(entry)] = digest
        elif entry.parts[0].endswith(".dist-info"):
            metadata[str(entry)] = pin_file(inputs, installed)
    python_files = {str(path.relative_to(TREE)) for path in (TREE / "docmancer").rglob("*.py")}
    if not product or python_files != {name for name in product if name.endswith(".py")}:
        raise ValueError("installed package omits or adds reviewed Python source files")
    scorer.verify_assets(str(args.model_dir))
    for name, digest in scorer.ASSETS.items():
        pin_file(inputs, args.model_dir / name, digest)
    pin_file(inputs, args.model_dir / "provenance.json")
    if not torch.cuda.is_available():
        raise ValueError("real pinned Qwen CUDA runtime is unavailable")
    runtime = {"torch": torch.__version__, "cuda": torch.version.cuda,
        **{name: importlib.metadata.version(name) for name in ("transformers", "tokenizers", "safetensors")},
        "capability": list(torch.cuda.get_device_capability(0)), "dtype": "bfloat16", "attention": "sdpa", "batch": 1}
    if runtime != scorer.RUNTIME:
        raise ValueError("pinned runtime mismatch")
    if sha(POLICY) != "16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11":
        raise ValueError("original frozen Qwen policy changed")
    record = {"runtime": runtime, "model_id": scorer.MODEL_ID,
        "model_revision": scorer.REVISION, "verified_assets": scorer.ASSETS,
        "policy_sha256": sha(POLICY), "matched_python_files": len(python_files),
        "installed_root": str(root), "preflight_model_forwards": 0,
        "boundary": "Preflight provenance before any client session; not cumulative live inference accounting.",
        "packaged_product": {"distribution": distribution.metadata["Name"], "version": distribution.version,
                             "files": product, "metadata_files": metadata}}
    return scorer.RECIPE, record


def prepare(args, inputs):
    import yaml
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    from docmancer.mcp.docs_server import call_docs_tool_payload

    project = args.work / "project"
    project.mkdir()
    descriptor = next(row for row in json.loads((DATA / "projects.json").read_text()) if row["id"] == "meridian")
    historical_sources = json.loads((HISTORY / "sources.json").read_text())
    for name in descriptor["project_documents"]:
        original = DATA / descriptor["root"] / name
        pin_file(inputs, original, historical_sources[name])
        (project / name).write_bytes(original.read_bytes())
    (project / "AGENTS.md").write_text("This documentation fixture is read-only. Never change its source documents.\n")
    catalog = {"schema_version": 1, "code_files": [],
        "documentation_languages": {name: ["en"] for name in descriptor["project_documents"]},
        "documents": [{"path": name, "role": "other", "scope": "project", "authority": "source_of_truth",
                       "status": "active", "impact": "track", "description": "Documentation source"}
                      for name in descriptor["project_documents"]]}
    (project / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False))
    sources = {path.name: sha(path) for path in project.iterdir()}
    if sources != historical_sources:
        raise ValueError("frozen catalog/instructions/source snapshot changed")
    save(args.output / "sources.json", sources)
    tasks = [row for row in json.loads((DATA / "tasks.json").read_text()) if row["id"] in CASES]
    if tasks != json.loads((HISTORY / "tasks.json").read_text()) or tuple(row["id"] for row in tasks) != CASES:
        raise ValueError("frozen questions/facts/order changed")
    save(args.output / "tasks.json", tasks)  # Outside all model-readable source roots.
    state = args.work / "docatlas-state"
    state.mkdir(mode=0o700)
    env = {"DOCATLAS_HOME": str(state), "DOCATLAS_OFFLINE": "1", "DOCATLAS_AUTO_VECTORS": "0",
           "DOCATLAS_CONTEXT_COMPRESSION": "off", "ORT_DISABLE_TELEMETRY": "1"}
    with server_environment(env):
        service = create_local_mcp_service()
        storage = service.member_storage_policy
        cat = read_project_docs_catalog(project)
        exists = storage.validate(project, service.config.index.db_path)
        result = call_docs_tool_payload("prepare_docs", {"action": "sync_project_docs", "project_path": str(project),
            "mutation": {"operation": "sync_project_docs", "confirm": True, "storage_path": str(storage.db_path),
                "expected_generation_id": storage.generation() if exists else None,
                "catalog_sha256": sha(project / "docatlas.project-docs.yaml"),
                "documents": [{"path": row.path, "content_sha256": sha(project / row.path),
                               "catalog_entry_hash": catalog_entry_hash(row)} for row in cat.entries]}}, service)
        save(args.output / "preparation.json", result)
        if result.get("status") != "success":
            raise RuntimeError("public project preparation failed; inspect preparation.json")
    return project, tasks, env, Path(storage.db_path), sources


def prepare_sessions(args, project, tasks, env, recipe, inputs):
    """Build every arm before inference; compare only declared backend differences."""
    profile = module("step13_profile_builder", PROFILE / "documentation_profile.py")
    common = (PROFILE / "profile/common.txt").read_text(encoding="utf-8").strip()
    common_sha = hashlib.sha256(common.encode()).hexdigest()
    baselines, jobs, shared_baseline = {}, [], None
    for task in tasks:
        for arm in ARMS:
            backend = "files" if arm == "files" else "mcp"
            location, out = args.work / arm / task["id"], args.output / arm / task["id"]
            location.mkdir(parents=True)
            out.mkdir(parents=True)
            selected = dict(env)
            link_policy = "one-hop-v1" if arm == "qwen-one-hop" else "off"
            if backend == "mcp":
                selected.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="1", DOCATLAS_MINIMAL_CONTEXT_RECIPE=recipe,
                    DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH=str(args.model_dir), DOCATLAS_MINIMAL_CONTEXT_POLICY=str(POLICY),
                    DOCATLAS_CONTEXT_LINKS=link_policy)
            config, receipt = profile.build_profile(project_root=project, workspace=location,
                backend=backend, executable=args.docatlas, python=Path(sys.executable), server_environment=selected,
                agent_name="measure", model=MODEL, frozen=True, max_steps=12,
                instruction_variant=args.instruction_variant)
            if (receipt["instruction_variant"] != args.instruction_variant or receipt["backend"] != backend or
                    config["plugins"][0]["options"].get("instructionVariant", "standard") != args.instruction_variant or
                    receipt["common_prompt_sha256"] != common_sha or
                    not config["agents"]["measure"]["system"].startswith(common + "\n\n")):
                raise ValueError("profile common instructions or requested variant differ")
            for name, digest in receipt["inputs"].items():
                pin_file(inputs, PROFILE / name, digest)
            normalized = deepcopy(config)
            if backend == "mcp":
                server = normalized["mcp"]["servers"]["docatlas"]
                binding = json.loads(server["environment"]["DOCATLAS_PROJECT_BINDING"])
                if (binding["workspace_path"] != str(location.resolve()) or
                        binding["project_path"] != str(project.resolve()) or
                        server["command"] != [str(args.docatlas), "mcp", "docs-serve"] or
                        server["environment"]["DOCATLAS_CONTEXT_LINKS"] != link_policy):
                    raise ValueError("unexpected MCP binding, command or link policy")
                binding["workspace_path"] = "<session-workspace>"
                server["environment"]["DOCATLAS_PROJECT_BINDING"] = json.dumps(binding, sort_keys=True)
                server["environment"]["DOCATLAS_CONTEXT_LINKS"] = "<declared-link-policy>"
            elif "mcp" in normalized:
                raise ValueError("files control must not start MCP")
            if baselines.setdefault(backend, normalized) != normalized:
                raise ValueError("unexpected within-backend configuration difference")
            shared = deepcopy(normalized)
            shared.pop("mcp", None)
            for key in ("system", "permissions"):
                shared["agents"]["measure"].pop(key)
            for key in ("backend", "fileSnapshot"):
                shared["plugins"][0]["options"].pop(key, None)
            for key in ("tools", "guard_tools"):
                shared["plugins"][1]["options"].pop(key)
            if shared_baseline is None:
                shared_baseline = shared
            if shared != shared_baseline:
                raise ValueError("unexpected cross-backend configuration difference")
            registry = out / "mcp-process.json"
            if backend == "mcp":
                server = config["mcp"]["servers"]["docatlas"]
                server["command"] = [str(Path(sys.executable)), "-I", str(HERE / "owned_mcp.py"),
                                     "--registry", str(registry), "--", *server["command"]]
            config["plugins"].append({"package": str(OBSERVER), "options": {"output": str(out / "capture")}})
            save(location / "opencode.json", config)
            save(out / "config.json", config)
            save(out / "profile.json", receipt)
            with (out / "question.txt").open("x", encoding="utf-8") as stream:
                stream.write(task["question"])
            for path in (location / "opencode.json", out / "config.json", out / "profile.json", out / "question.txt"):
                pin_file(inputs, path)
            jobs.append({"arm": arm, "case": task["id"], "location": location, "output": out,
                         "registry": registry if backend == "mcp" else None, "question": task["question"]})
    if len(jobs) != 12 or set(baselines) != {"mcp", "files"}:
        raise ValueError("incomplete frozen session roster")
    return jobs, common_sha


def live(args):
    for path in (args.opencode, args.docatlas, args.model_dir, args.work, args.output):
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("all host paths must be literal absolute paths")
    if args.docatlas.parent != Path(sys.executable).parent:
        raise ValueError("run with the Python from the same installed environment as doc-atlas")
    if args.work.resolve().is_relative_to(TREE) or args.work.exists() or args.output.exists():
        raise ValueError("work must be new and outside checkout; output must be new (never automatic reruns)")
    if args.work.is_relative_to(args.output) or args.output.is_relative_to(args.work):
        raise ValueError("source workspace and output archives must be disjoint")
    if not 0 < args.timeout <= 900:
        raise ValueError("session timeout must be positive and no greater than the declared 900 seconds")
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"model": MODEL, "arms": list(ARMS), "cases": list(CASES), "sessions": 12,
        "instruction_variant": args.instruction_variant, "maximum_steps": 12,
        "timeout_seconds_per_session": args.timeout, "maximum_preparations": 1,
        "launch": "OpenCode --standalone; held private group + explicit MCP PID/start/namespace registration and pidfd cleanup",
        "automatic_reruns": False, "stop_before_next_case_on_failure": True,
        "source_scope": "six unchanged Meridian project docs; excluded module absent in all arms",
        "runner_sha256": sha(Path(__file__)), "session_runtime_sha256": sha(HERE / "session_runtime.py"),
        "owned_mcp_sha256": sha(HERE / "owned_mcp.py"),
        "boundary": "New diagnostic, not a paired standard-vs-concise trial or a default-rollout gate."}
    save(args.output / "plan.json", plan)
    summary = {"status": "preflight", "results": [], "quality": "not_graded", "model_call_count": None}
    try:
        inputs = {}
        for path in (Path(__file__).resolve(), HERE / "session_runtime.py", HERE / "owned_mcp.py", POLICY,
                     args.opencode, args.docatlas, Path(sys.executable), TREE / "pyproject.toml",
                     PROFILE / "documentation_profile.py", PROFILE / "profile/common.txt",
                     OBSERVER / "index.js", OBSERVER / "package.json", DATA / "projects.json", DATA / "tasks.json",
                     HISTORY / "sources.json", HISTORY / "tasks.json"):
            pin_file(inputs, path)
        version = subprocess.run([str(args.opencode), "--version"], text=True, capture_output=True,
                                 check=True, timeout=15).stdout.strip()
        if version != "opencode v2.2.5":
            raise ValueError("unqualified OpenCode version: " + version)
        recipe, runtime = verify_runtime(args, inputs)
        save(args.output / "runtime.json", {**runtime, "opencode_version": version, "python": sys.version,
                                           "python_executable": sys.executable})
        args.work.mkdir(mode=0o700)
        project, tasks, env, database, sources = prepare(args, inputs)
        db_before = pin_file(inputs, database)
        for name, digest in sources.items():
            pin_file(inputs, project / name, digest)
        jobs, common_sha = prepare_sessions(args, project, tasks, env, recipe, inputs)
        for name in ("plan.json", "runtime.json", "preparation.json", "sources.json", "tasks.json"):
            pin_file(inputs, args.output / name)
        manifest = {"format": "step13-frozen-inputs-v1", "files": inputs,
            "checkout_commit": subprocess.run(["git", "-C", str(TREE), "rev-parse", "HEAD"], text=True,
                                              capture_output=True, check=True, timeout=15).stdout.strip(),
            "identity_authority": "File hashes include working changes; commit alone is not the candidate identity.",
            "packaged_product_manifest": "runtime.json:packaged_product (distribution files, including non-Python assets)",
            "instruction_variant": args.instruction_variant, "common_prompt_sha256": common_sha,
            "checked_configuration_differences": {
                "within_mcp": ["binding.workspace_path", "DOCATLAS_CONTEXT_LINKS"], "within_files": [],
                "between_backends": ["backend system paragraph", "permissions", "MCP server",
                    "profile backend/fileSnapshot", "adapter tools/guard_tools"],
                "launch_paths_only": ["owned MCP registry", "observer capture directory"]},
            "sessions": [{key: str(value) if isinstance(value, Path) else value
                          for key, value in job.items() if key != "question"} for job in jobs],
            "boundary": "Frozen file bytes/resolved paths, not a complete OS/provider snapshot or quality audit."}
        save(args.output / "input-manifest.json", manifest)
        summary.update(sessions_prepared=len(jobs), frozen_input_count=len(inputs),
                       input_manifest_sha256=pin_file(inputs, args.output / "input-manifest.json"))
        client_env = {key: value for key, value in os.environ.items() if not key.startswith("DOCATLAS_")}
        summary["status"] = "running"
        for job in jobs:
            arm, case, out, registry = (job[key] for key in ("arm", "case", "output", "registry"))
            changed = input_drift(inputs)
            if changed:
                summary.update(status="stopped_on_input_drift", input_drift={"before_arm": arm,
                               "before_case": case, "changed_files": changed})
                return 1
            attempt = {"arm": arm, "case": case, "process_started": None,
                       "receipt_available": False, "session_status": "starting"}
            summary["results"].append(attempt)
            try:
                launched = RUNTIME.launch_session(opencode=args.opencode, location=job["location"], question=job["question"],
                    env=client_env, output=out / "session", model=MODEL, agent="measure", timeout=args.timeout,
                    title=f"Meridian {arm} {case}", owned_process_files=(registry,) if registry else ())
            finally:
                receipt_path = out / "session/receipt.json"
                if receipt_path.exists():
                    captured = json.loads(receipt_path.read_text())
                    attempt.update(receipt_available=True, **{key: captured[key] for key in (
                        "process_started", "session_status", "retrieval_status", "answer_status", "transport_pass")})
            result = launched["receipt"]
            (out / "final-answer.txt").write_text(result["answer"], encoding="utf-8")
            unchanged = {path.name: sha(path) for path in project.iterdir()} == sources and sha(database) == db_before
            attempt["sources_and_database_unchanged"] = unchanged
            if not result["transport_pass"] or not unchanged:
                summary["status"] = "stopped_on_first_failure"
                return 1
        summary["status"] = "all_sessions_completed; answer_quality_not_graded"
        return 0
    except BaseException as exc:
        summary["status"] = "failed"
        summary["exception_type"] = type(exc).__name__
        raise
    finally:
        summary["sessions_with_receipts"] = sum(row["receipt_available"] for row in summary["results"])
        summary["sessions_started"] = sum(row["process_started"] is True for row in summary["results"])
        summary["session_start_unknown"] = sum(row["process_started"] is None for row in summary["results"])
        summary["sessions_not_started"] = 12 - summary["sessions_started"] - summary["session_start_unknown"]
        save(args.output / "summary.json", summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    replay = commands.add_parser("classify-history", help="Offline only; no client, product or model calls")
    replay.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run", help="One real, separately authorized twelve-session experiment; never retries")
    for name in ("opencode", "docatlas", "model-dir", "work", "output"):
        run.add_argument("--" + name, type=Path, required=True)
    run.add_argument("--instruction-variant", choices=("standard", "concise-v1"), default="standard")
    run.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    return classify_history(args.output) if args.action == "classify-history" else live(args)


if __name__ == "__main__":
    raise SystemExit(main())
