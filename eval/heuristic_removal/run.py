"""Sequential public in-process comparison, never an installed-stdio claim.

Selective reuse: old runner's cold prepare, source snapshots, read-only equality,
durable receipts and bounded calls. No old RAS flags, stage helpers or oracle imports.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr
import importlib.metadata
import io
import json
import os
from pathlib import Path
import resource
import importlib.util
import subprocess
import sys
import time
import traceback
import zipfile

# Script execution under -I exposes only this harness, never checkout docmancer.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import database, deadline, files, integrity, ledger, pack, save, sha, snapshots

REPO = Path(__file__).resolve().parents[2]
ARMS = {"V0": "", "VQ": "Q", "VA": "A", "VS": "S", "VALL": "ALL"}
ARM_ENV = "DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL"


def load_dataset(directory):
    if (directory / "source_plan.json").is_file():
        cases = json.loads((directory / "questions.json").read_bytes())["cases"]
        families = json.loads((directory / "source_plan.json").read_bytes())["families"]
    else:
        # D's published INTERFACE.md. Coordinator calls this only AFTER code freeze.
        sealed_manifest = json.loads((directory / "FREEZE_MANIFEST.json").read_bytes())
        for item in sealed_manifest["files"]:
            if sha((directory / item["path"]).read_bytes()) != item["sha256"]:
                raise ValueError("D independent source/sealed digest mismatch")
        cases = json.loads((directory / "sealed/questions.json").read_bytes())["cases"]
        sources = json.loads((directory / "source-manifest.json").read_bytes())["sources"]
        groups = sorted({row["project_group"] for row in sources})
        families = [dict(id=group, paths=[Path(row["path"]).relative_to(Path("corpus") / group).as_posix()
                    for row in sources if row["project_group"] == group]) for group in groups]
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("duplicate case id")
    known = {family["id"] for family in families}
    if any(case["project_group"] not in known or not isinstance(case["question"], str) for case in cases):
        raise ValueError("invalid public dataset")
    return cases, families


def source_directory(dataset, family):
    return dataset / ("sources" if (dataset / "source_plan.json").is_file() else "corpus") / family


def freeze(config_path, manifest_path):
    if manifest_path.exists():
        raise ValueError("freeze manifest already exists")
    config = json.loads(config_path.read_bytes())
    if config.get("runtime_authorized") is not True or not config.get("authorization_reference"):
        raise ValueError("current checkpoint forbids runtime; explicit coordinator authorization required")
    if config.get("common"):
        raise ValueError("no legacy experiment flags: actual HEAD default is V0")
    code_freeze = Path(config["code_freeze_manifest"])
    if sha(code_freeze.read_bytes()) != config["code_freeze_sha256"]:
        raise ValueError("coordinator code-freeze receipt missing or changed; do not open D sealed questions")
    if config["limits"] != dict(context_calls=340, call_seconds=60, prepare_seconds=180, wall_seconds=1800):
        raise ValueError("limits must match the proposed frozen ceiling; stricter checkpoints require coordinator revision")
    paths = [config_path.resolve(), REPO / "pyproject.toml", REPO / "eval/evidence_quality_v2/runtime.py",
             REPO / "tests/test_heuristic_removal_public_integration.py",
             REPO / "tests/test_prepared_retrieval_integration.py",
             REPO / "eval/prepared_model_comparison40/evaluate.py"]
    for directory in (REPO / "docmancer", REPO / "eval/heuristic_removal"):
        paths += [p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    for specification in config["datasets"]:
        directory = Path(specification["path"]).resolve()
        cases, _ = load_dataset(directory)
        if len(cases) != specification["count"]:
            raise ValueError("exact frozen dataset count mismatch")
        paths += [p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += [Path(p).resolve() for p in config["freeze_files"]]
    paths += [code_freeze.resolve(), Path(config["baseline_wheel"]).resolve(), Path(config["candidate_wheel"]).resolve()]
    planned = sum(spec["count"] * len(spec["arms"]) for spec in config["datasets"])
    if planned != 340 or [spec["count"] for spec in config["datasets"]] != [40, 20, 20]:
        raise ValueError("required historical60 x5 + new20 x2 design")
    if any(spec["arms"] != (list(ARMS) if index < 2 else ["V0", "VALL"])
           for index, spec in enumerate(config["datasets"])):
        raise ValueError("invalid frozen arms")
    manifest = dict(schema_version=1, config=config,
                    base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                    inputs_sha256={str(p): sha(p.read_bytes()) for p in sorted(set(paths))},
                    boundary="public in-process MCP dispatcher; real isolated member SQLite; NOT stdio/client/production",
                    arm_env=ARM_ENV, arms=ARMS, planned_context_calls=planned,
                    baseline="pinned base91dd2b4e installed wheel interpreter; no previous RAS flags",
                    generator_status="NOT MEASURED", python=sys.version,
                    dependencies={name: importlib.metadata.version(name) for name in ("doc-atlas", "mcp", "tiktoken")})
    save(manifest_path, manifest)


def verify(manifest):
    changed = [name for name, digest in manifest["inputs_sha256"].items() if sha(Path(name).read_bytes()) != digest]
    if changed:
        raise ValueError("frozen files changed: " + repr(changed))


def run(manifest_path, output, work, worker=None):
    manifest = json.loads(manifest_path.read_bytes())
    verify(manifest)
    config = dict(manifest["config"])
    if not config.get("runtime_authorized"):
        raise ValueError("runtime not authorized")
    if worker is None:
        return orchestrate(manifest_path, manifest, output, work)
    worker = json.loads(worker.read_bytes())
    config["datasets"] = worker["datasets"]
    call_cap = sum(spec["count"] for spec in config["datasets"])
    if not config.get("runtime_authorized"):
        raise ValueError("runtime not authorized")
    if output.exists() or work.exists():
        raise ValueError("fresh output and work required; attempts never overwritten")
    output.mkdir(parents=True)
    work.mkdir(parents=True, mode=0o700)
    # Load only the established environment fixture by explicit file. Its product
    # imports resolve exclusively to this interpreter's installed wheel.
    runtime_spec = importlib.util.spec_from_file_location("heuristic_removal_fixture_runtime", REPO / "eval/evidence_quality_v2/runtime.py")
    runtime = importlib.util.module_from_spec(runtime_spec)
    runtime_spec.loader.exec_module(runtime)
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application.query_trace import query_trace
    import docmancer
    import tiktoken
    origin = Path(docmancer.__file__).resolve()
    if origin.is_relative_to(REPO) or not origin.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("comparison must use installed wheel in selected interpreter, not checkout")
    if str(Path(sys.executable).resolve()) != str(Path(worker["python"]).resolve()):
        raise ValueError("wrong baseline/candidate interpreter")
    if Path(sys.prefix).resolve() != Path(worker["python"]).parent.parent.resolve():
        raise ValueError("wrong baseline/candidate prefix")
    arm = worker["datasets"][0]["arms"][0]
    wheel = Path(config["baseline_wheel" if arm == "V0" else "candidate_wheel"])
    installed_files = {}
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith("docmancer/") and not name.endswith("/"):
                expected = sha(archive.read(name))
                target = origin.parent.parent / name
                if not target.is_file() or sha(target.read_bytes()) != expected:
                    raise ValueError("installed artifact differs from frozen wheel: " + name)
                installed_files[name] = expected
    save(output / "INSTALLED_ORIGIN.json", dict(python=sys.executable, prefix=sys.prefix, origin=str(origin),
         wheel=str(wheel), wheel_sha256=sha(wheel.read_bytes()), installed_files_sha256=installed_files))
    if config.get("tokenizer_cache_dir"):
        os.environ["TIKTOKEN_CACHE_DIR"] = config["tokenizer_cache_dir"]
    tokenizer = tiktoken.get_encoding("o200k_base")
    # Cache asset must be supplied and hashed in freeze_files before this call.
    summary = dict(status="running", preparations=0, contexts=0, resources=0, model_calls=0,
                   installed_origin=str(Path(docmancer.__file__).resolve()), records=[], stopped_arms=[])
    started = time.perf_counter()
    stopped = set()
    ledger_path = output / "EXECUTION_LEDGER.jsonl"
    original_env = dict(os.environ)
    try:
        for spec in config["datasets"]:
            dataset_index = spec["index"]
            dataset = Path(spec["path"]).resolve()
            cases, families = load_dataset(dataset)
            for family in families:
                selected = [case for case in cases if case["project_group"] == family["id"]]
                if "case_ids" in spec:
                    # Recovery only: completed/started IDs are never replayed.
                    selected = [case for case in selected if case["id"] in spec["case_ids"]]
                if not selected:
                    continue
                group = f'{dataset_index}-{family["id"]}'
                root = (work / group / "project").resolve()
                documents = {}
                for name in family["paths"]:
                    source = (source_directory(dataset, family["id"]) / name).resolve()
                    if not source.is_relative_to(source_directory(dataset, family["id"]).resolve()):
                        raise ValueError("source escapes pinned family")
                    documents[name] = source.read_bytes().decode("utf-8")
                runtime.write_project(root, documents)
                with runtime.isolated_service(work / group / "state") as (service, service_config):
                    if time.perf_counter() - started >= worker["wall_seconds"]:
                        raise TimeoutError("overall comparison wall ceiling")
                    summary["preparations"] += 1
                    ledger(ledger_path, "prepare_docs", "started", family=group)
                    with deadline(min(180, max(1, int(worker["wall_seconds"] - (time.perf_counter() - started))))):
                        inventory = runtime.index_project(service, service_config, root)
                    committed = snapshots(inventory, root, documents)
                    initial_db, initial_files = database(inventory["storage_path"]), files(root)
                    save(output / "preparation" / f"{group}.json", dict(root=str(root), inventory=inventory,
                         snapshot_sources=committed, dataset=str(dataset), family=family["id"]))
                    ledger(ledger_path, "prepare_docs", "returned", family=group, seconds=inventory["seconds"])
                    for case_index, case in enumerate(selected):
                        arms = spec["arms"]
                        arms = arms[case_index % len(arms):] + arms[:case_index % len(arms)]
                        for arm in arms:
                            if arm in stopped:
                                continue
                            verify(manifest)
                            if summary["contexts"] >= call_cap or time.perf_counter() - started >= worker["wall_seconds"]:
                                raise TimeoutError("comparison call/wall ceiling")
                            for key in tuple(os.environ):
                                if key.startswith("DOCATLAS_EXPERIMENT_"):
                                    del os.environ[key]
                            if ARMS[arm]:
                                os.environ[ARM_ENV] = ARMS[arm]
                            os.environ["DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS"] = str(config["packing_tokens"])
                            arguments = dict(question=case["question"], project_path=str(root), scope="project")
                            destination = output / "calls" / str(dataset_index) / case["id"] / arm
                            trace = io.StringIO()
                            metadata = dict(case_id=case["id"], variant=arm, dataset=str(dataset), family=group,
                                            public_request=arguments, status="started", model_calls=0)
                            save(destination / "metadata.json", metadata)
                            summary["contexts"] += 1
                            ledger(ledger_path, "get_docs_context", "started", case_id=case["id"], arm=arm)
                            call_start, cpu = time.perf_counter(), time.process_time()
                            try:
                                remaining = max(1, int(worker["wall_seconds"] - (time.perf_counter() - started)))
                                with redirect_stderr(trace), query_trace(config["trace"]), deadline(min(60, remaining)):
                                    payload = call_docs_tool_payload("get_docs_context", arguments, service)
                                # Persist native public bytes before independent assessment/packing.
                                save(destination / "public-payload.json", payload)
                                wire = (destination / "public-payload.json").read_bytes()
                                checks = integrity(payload, root, documents)
                                save(destination / "integrity.json", checks)
                                save(destination / "packed.json", pack(payload, tokenizer, config["packing_tokens"]))
                                metadata.update(status="returned", integrity_errors=checks["errors"],
                                                raw_sha256=sha(wire), utf8_bytes=len(wire),
                                                tokens=len(tokenizer.encode(wire.decode(), disallowed_special=())))
                                if checks["errors"]:
                                    stopped.add(arm)
                                    ledger(ledger_path, "arm_stop", "integrity_error", arm=arm, errors=checks["errors"])
                            except Exception as exc:
                                metadata.update(status="error", error=str(exc), traceback=traceback.format_exc())
                                # A failed context is never repaired/retried; prevent unknown safety from continuing.
                                stopped.add(arm)
                            metadata.update(seconds=time.perf_counter() - call_start,
                                            cpu_seconds=time.process_time() - cpu,
                                            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                            database_unchanged=database(inventory["storage_path"]) == initial_db,
                                            files_unchanged=files(root) == initial_files)
                            (destination / "trace.jsonl").write_text(trace.getvalue())
                            save(destination / "metadata.json", metadata)
                            summary["records"].append(metadata)
                            ledger(ledger_path, "get_docs_context", metadata["status"], case_id=case["id"], arm=arm,
                                   seconds=metadata["seconds"])
                            save(output / "SUMMARY.json", summary)
                            if not metadata["database_unchanged"] or not metadata["files_unchanged"]:
                                raise ValueError("read-only state violation; stop whole run")
        verify(manifest)
        summary["status"] = "completed" if not stopped and summary["contexts"] == call_cap else "incomplete_or_integrity_failure"
    except Exception as exc:
        summary.update(status="error", error=str(exc), traceback=traceback.format_exc())
        ledger(ledger_path, "workload", "error", error=str(exc))
    finally:
        os.environ.clear()
        os.environ.update(original_env)
        summary.update(seconds=time.perf_counter() - started, stopped_arms=sorted(stopped))
        save(output / "SUMMARY.json", summary)
    return 0 if summary["status"] == "completed" else 1


def orchestrate(manifest_path, manifest, output, work):
    """Installed subprocess lanes; sequential, fixed V0/Q/A/S/ALL order, no retry."""
    if output.exists() or work.exists():
        raise ValueError("fresh coordinator output/work required")
    output.mkdir(parents=True)
    work.mkdir(parents=True, mode=0o700)
    config = manifest["config"]
    started = time.perf_counter()
    result = dict(status="running", contexts=0, preparations=0, model_calls=0, arms={})
    try:
        for arm in ARMS:
            verify(manifest)
            remaining = int(1800 - (time.perf_counter() - started))
            if remaining <= 0:
                raise TimeoutError("overall engine wall ceiling")
            specs = [dict(spec, index=index, arms=[arm]) for index, spec in enumerate(config["datasets"])
                     if arm in spec["arms"]]
            interpreter = config["baseline_python" if arm == "V0" else "candidate_python"]
            lane = dict(python=interpreter, datasets=specs, wall_seconds=remaining)
            worker_path = output / f"worker-{arm}.json"
            save(worker_path, lane)
            command = [interpreter, "-I", str(Path(__file__).resolve()), "--manifest", str(manifest_path.resolve()),
                       "--output", str((output / arm).resolve()), "--work", str((work / arm).resolve()),
                       "--worker", str(worker_path.resolve())]
            ledger(output / "EXECUTION_LEDGER.jsonl", "arm_process", "started", arm=arm, command=command)
            with (output / f"{arm}.stdout").open("w") as stdout, (output / f"{arm}.stderr").open("w") as stderr:
                child = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=remaining, cwd=work,
                                       env={key: value for key, value in os.environ.items()
                                            if key != "PYTHONPATH" and not key.startswith("DOCATLAS_")})
            summary_path = output / arm / "SUMMARY.json"
            summary = json.loads(summary_path.read_bytes()) if summary_path.exists() else dict(status="setup_failure", contexts=0, preparations=0)
            result["arms"][arm] = summary
            result["contexts"] += summary["contexts"]
            result["preparations"] += summary["preparations"]
            ledger(output / "EXECUTION_LEDGER.jsonl", "arm_process", "returned", arm=arm, exit_code=child.returncode,
                   contexts=summary["contexts"], preparations=summary["preparations"])
            if result["contexts"] > 340:
                raise ValueError("global context ceiling")
        result["status"] = "completed" if result["contexts"] == 340 and all(
            lane["status"] == "completed" for lane in result["arms"].values()) else "incomplete_or_failed"
    except Exception as exc:
        result.update(status="error", error=str(exc), traceback=traceback.format_exc())
    finally:
        # Started receipts remain authoritative even if an outer timeout kills a
        # worker before SUMMARY.json. Never omit a timed-out attempt from costs.
        attempts = []
        for path in output.glob("*/EXECUTION_LEDGER.jsonl"):
            attempts.extend(json.loads(line) for line in path.read_text().splitlines())
        result["contexts"] = sum(row["operation"] == "get_docs_context" and row["status"] == "started" for row in attempts)
        result["preparations"] = sum(row["operation"] == "prepare_docs" and row["status"] == "started" for row in attempts)
        result["raw_attempt_ledger_rows"] = len(attempts)
        result["seconds"] = time.perf_counter() - started
        save(output / "SUMMARY.json", result)
    return 0 if result["status"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.freeze:
        freeze(args.config, args.manifest)
        return 0
    return run(args.manifest, args.output, args.work, args.worker)


if __name__ == "__main__":
    raise SystemExit(main())
