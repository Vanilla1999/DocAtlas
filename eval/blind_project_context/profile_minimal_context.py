"""Censored real public-read profiler, independent of product runtime policy.

Use the measured server's Python and config. Installed imports are required unless
--source-root explicitly selects a development comparison; no wheel is modified.
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import os
from pathlib import Path
import pstats
import signal
import sys
import time
import traceback


class DiagnosticDeadline(BaseException):
    """Do not let application Exception handlers turn cancellation into success."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--seconds", type=int, default=30,
                        help="Diagnostic alarm duration; never a product quota")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    config = args.config.resolve()
    source_root = args.source_root.resolve() if args.source_root else None
    server = json.loads(config.read_text())["mcp"]["servers"]["docatlas"]
    for key in list(os.environ):
        if key.startswith("DOCATLAS_") or key == "PYTHONPATH":
            del os.environ[key]
    os.environ.update(server["environment"])
    os.chdir(server["cwd"])
    if source_root:
        sys.path.insert(0, str(source_root))
    import docmancer
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    from docmancer.docs.application.minimal_context_selection import observe_minimal_context
    module = Path(docmancer.__file__).resolve()
    assert module.is_relative_to(source_root) if source_root else "site-packages" in module.parts
    root = Path(server["cwd"])
    watched = sorted((root / "project").rglob("*.md")) + sorted((root / "docatlas-home").rglob("*.db"))

    def hashes():
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in watched}

    before = hashes()
    request = {"question": "Что от меня ожидается, когда я отправляю pull request в DocAtlas?"}
    receipt = {"schema": "bounded-public-profile-v2", "python": sys.executable,
               "module": str(module), "config": str(config),
               "import_mode": "source_comparison" if source_root else "installed",
               "request": request, "diagnostic_seconds": args.seconds,
               "result_claim": "diagnostic_only_not_product_success",
               "model_counters": None}

    def deadline(signum, frame):
        receipt["interrupted_stack"] = traceback.format_stack(frame)
        cursor = frame
        while cursor is not None:
            if (cursor.f_code.co_name == "score_complete_units"
                    and cursor.f_code.co_filename.endswith("complete_context_scoring.py")):
                # Read actual counters; never replace scorer/model or infer pairs
                # from batch count. Completed forwards only; current work may be
                # in flight and is explicitly not counted as completed.
                receipt["model_counters"] = dict(cursor.f_locals.get("receipt", {}))
                receipt["model_counter_boundary"] = "completed_batches_at_alarm"
            elif (cursor.f_code.co_name == "select_minimal_context"
                    and isinstance(cursor.f_locals.get("scoring"), dict)
                    and receipt["model_counters"] is None):
                receipt["model_counters"] = dict(cursor.f_locals["scoring"])
                receipt["model_counter_boundary"] = "completed_scorer_before_alarm"
            cursor = cursor.f_back
        raise DiagnosticDeadline()

    previous = signal.signal(signal.SIGALRM, deadline)
    profile = cProfile.Profile()
    started = time.perf_counter()
    profile.enable()
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    observations = []
    try:
        service = create_local_mcp_service()
        with observe_minimal_context() as observations:
            result = call_docs_tool_payload("get_docs_context", request, service)
        receipt.update(outcome="completed_before_diagnostic_deadline", product_status=result.get("status"),
                       source_selection=result.get("source_selection"))
    except DiagnosticDeadline:
        receipt["outcome"] = "diagnostic_aborted"
    except BaseException as exc:
        receipt.update(outcome="exception", exception=repr(exc), traceback=traceback.format_exc())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        profile.disable()
        signal.signal(signal.SIGALRM, previous)
        receipt["elapsed_seconds"] = time.perf_counter() - started
        profile.dump_stats(str(args.out / "public-call.prof"))
    if observations:
        receipt["model_counters"] = dict(observations[-1]["receipt"])
        receipt["model_counter_boundary"] = "completed_scorer_observation"
    phase_names = {"run", "prepare", "prepare_dependency_sets", "_qualify_candidate_lookups",
                   "build_units", "score_complete_units", "flush", "close_selection",
                   "source_graph", "parse_markdown_parents", "_to_dict", "select_evidence",
                   "project_native_rank_context", "recheck_structural_row"}
    receipt["phases"] = [
        {"file": item.code.co_filename, "function": item.code.co_name,
         "calls": item.callcount, "cumulative_seconds": item.totaltime,
         "own_seconds": item.inlinetime}
        for item in profile.getstats()
        if hasattr(item.code, "co_name") and item.code.co_name in phase_names
        and "/docmancer/" in item.code.co_filename
    ]
    if receipt["model_counters"] is None and not any(
        phase["function"] == "score_complete_units" for phase in receipt["phases"]
    ):
        receipt["model_counters"] = {"model_pairs": 0, "model_forwards": 0, "model_load_attempts": 0}
        receipt["model_counter_boundary"] = "scorer_not_entered"
    after = hashes()
    receipt.update(inputs_unchanged=after == before, watched_file_count=len(before))
    code_root = module.parent
    receipt["code_sha256"] = {
        name: hashlib.sha256((code_root / name).read_bytes()).hexdigest()
        for name in ("docs/application/source_reference_evidence.py",
                     "docs/domain/original_body_discovery.py",
                     "docs/application/_project_docs_service_part03.py",
                     "docs/application/complete_context_scoring.py")
    }
    (args.out / "source-hashes.json").write_text(json.dumps({"before": before, "after": after}, indent=2))
    (args.out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    for order in ("cumulative", "tottime"):
        stream = io.StringIO()
        pstats.Stats(profile, stream=stream).strip_dirs().sort_stats(order).print_stats(45)
        (args.out / f"{order}.txt").write_text(stream.getvalue())
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
