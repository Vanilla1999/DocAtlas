"""Portable public-acquisition structural-stage diagnostic, not a calibration test.

Run from the repository root with the supported environment::

    python -m eval.blind_project_context.probe_minimal_structure --model-dir MODEL_DIR

This preserves the independently authored /tmp diagnostic's documents and
assertions. A profile return hook exercises structural closure while native
provenance is live. It does not replace retrieval, selection or validation, and
does not assert calibrated final-packet membership or answering-model quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from docmancer.docs.application.minimal_context_structure import (
    StructuralContextError, build_units, close_selection, recheck_structural_row,
)
from docmancer.mcp.docs_server import call_docs_tool_payload
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project


DOCUMENTS = {
    "docs/guide.md": (
        "# Guide\n\nScope introduction.\n\n## Empty\n\n### Selected\n\n"
        "Keep this condition [limits](#limits) and [more][ref].\n\n"
        "| Item | Value |\n| --- | --- |\n| A | B[^note] |\n\n"
        "#### Tail\n\nTail condition stays.\n\n## Noise\n\nUnselected noise.\n\n"
        "## Limits\n\nLimit condition [cycle](#selected).\n\n## Notes\n\n"
        "[^note]: Footnote condition.\n    Continued footnote.\n\n"
        "[ref]:\n  other.md#remote\n"
    ),
    "docs/other.md": (
        "# Other\n\nOther introduction.\n\n## Remote\n\n"
        "Remote condition [missing](private.md#hidden).\n"
    ),
}
QUESTION = "Explain the selected conditions and their limits."
BOUNDARY = "public MCP acquisition; observed structural output before model selection"


def run_fit_correction(model_dir: Path, work_dir: Path, *, observer_parity: bool = False) -> dict:
    """Two real public diagnostic calls; no threshold or semantic acceptance."""
    from docmancer.docs.application.complete_context_scoring import WINDOW_RECIPE, FIT_WINDOW_RECIPE
    from docmancer.docs.application.minimal_context_selection import observe_minimal_context
    from eval.blind_project_context.calibrate_minimal_context import db_digest
    from contextlib import nullcontext
    from docmancer.docs.application.complete_context_scoring import score_complete_units

    documents = dict(DOCUMENTS)
    documents["docs/guide.md"] = documents["docs/guide.md"].replace(
        "Scope introduction.", "Scope introduction. " + "The station operates during winter. " * 48)
    documents["docs/other.md"] += (
        "\n## Long procedure\n\n" + "Record the measured pressure before continuing. " * 100
        + "\nDo not restart until the isolation certificate is signed.\n")
    settings = {
        "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "1",
        "DOCATLAS_EXPERIMENT_MINI_PATH": str(model_dir.resolve()),
        "DOCATLAS_CONTEXT_COMPRESSION": "off",
        "DOCATLAS_MINIMAL_CONTEXT_POLICY": None,
        "DOCATLAS_MINIMAL_CONTEXT_RECIPE": WINDOW_RECIPE,
    }
    previous = {key: os.environ.get(key) for key in settings}
    results, packets = {}, {}
    raw_scoring = {}
    try:
        for key, value in settings.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        work_dir.mkdir(parents=True, exist_ok=False)
        project = work_dir / "project"
        write_project(project, documents)
        before_sources = {p: hashlib.sha256((project / p).read_bytes()).hexdigest() for p in documents}
        with isolated_service(work_dir / "state") as (service, config):
            for key, value in settings.items():
                if value is not None:
                    os.environ[key] = value
            index_project(service, config, project)
            before_db = db_digest(config.index.db_path)
            runs = (("off", FIT_WINDOW_RECIPE, False), ("on", FIT_WINDOW_RECIPE, True)) if observer_parity else (
                (WINDOW_RECIPE, WINDOW_RECIPE, True), (FIT_WINDOW_RECIPE, FIT_WINDOW_RECIPE, True))
            for name, recipe, observed in runs:
                os.environ["DOCATLAS_MINIMAL_CONTEXT_RECIPE"] = recipe
                captured = []

                def passive_return(frame, event, value):
                    if event == "return" and frame.f_code is score_complete_units.__code__:
                        captured.append(value)

                prior_profile = sys.getprofile()
                if observer_parity:
                    sys.setprofile(passive_return)
                try:
                    with observe_minimal_context() if observed else nullcontext([]) as observations:
                        packet = call_docs_tool_payload("get_docs_context", {
                            "question": QUESTION, "project_path": str(project), "scope": "project",
                        }, service)
                finally:
                    sys.setprofile(prior_profile)
                (work_dir / (name + ".json")).write_text(json.dumps(
                    {"packet": packet, "observations": observations, "passive_scorer_returns": captured},
                    ensure_ascii=False, indent=2))
                assert len(observations) == int(observed) and packet["source_selection"]["scan_complete"], packet
                if observer_parity:
                    assert len(captured) == 1
                    raw_scoring[name] = captured[0]
                assert packet["source_selection"]["calibration_status"] == "diagnostic_unverified"
                assert packet["context_quality"]["status"] == "unverified"
                for row in packet["sources"]:
                    raw = documents[row["path_or_url"]]
                    exact = "".join(raw.splitlines(keepends=True)[row["line_start"] - 1:row["line_end"]])
                    assert row["snippet"] == exact and row["scope"] == "project"
                    assert row["authority"] == "source_of_truth" and row["project_identity"]
                    material = {k: row.get(k) for k in ("section", "content", "snippet")}
                    material.update(content=exact, path=row["path_or_url"], version=None)
                    assert hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")).encode()).hexdigest() == row["content_sha256"]
                delivered = "\n".join(row["snippet"] for row in packet["sources"])
                for fact in ("Tail condition stays.", "Continued footnote.", "Remote condition",
                             "Do not restart until the isolation certificate is signed."):
                    assert fact in delivered
                assert db_digest(config.index.db_path) == before_db
                assert before_sources == {p: hashlib.sha256((project / p).read_bytes()).hexdigest() for p in documents}
                results[name] = observations[0] if observed else {"scores": captured[0][0], "receipt": captured[0][1]}
                packets[name] = packet
        if observer_parity:
            assert packets["off"] == packets["on"], "Observer changed public packet; raw packets saved"
            off_scores, off_receipt = raw_scoring["off"]
            on_scores, on_receipt = raw_scoring["on"]
            for key in ("model_pairs", "model_forwards", "model_input_tokens", "units"):
                assert off_receipt[key] == on_receipt[key]
            assert off_receipt["intervals_recorded"] == 0
            assert off_receipt["intervals_omitted"] == off_receipt["model_pairs"]
            assert on_receipt["intervals_recorded"] == on_receipt["model_pairs"]
            assert on_receipt["intervals_omitted"] == 0
            for off, on in zip(off_scores, on_scores, strict=True):
                assert "pair_token_intervals" not in off
                assert off["intervals_recorded"] == 0 and off["intervals_omitted"] == off["pairs"]
                assert len(on["pair_token_intervals"]) == on["intervals_recorded"] == on["pairs"]
                fields = {"pair_token_intervals", "intervals_recorded", "intervals_omitted"}
                assert {k: v for k, v in off.items() if k not in fields} == {k: v for k, v in on.items() if k not in fields}
            return {"status": "PASS", "boundary": "public in-process V4 observer OFF/ON, passive return hook; diagnostic keep-all",
                    "public_prepares": 1, "public_queries": 2, "exact_public_packet_parity": True,
                    "exact_scores_parity": True, "source_hashes": before_sources,
                    "logical_db_sha256": before_db, "receipts": {k: v[1] for k, v in raw_scoring.items()}}
        old = {s["identity"]: s for s in results[WINDOW_RECIPE]["scores"]}
        fixed = results[FIT_WINDOW_RECIPE]
        witnesses, long_units = [], []
        for score in fixed["scores"]:
            intervals = score["pair_token_intervals"]
            assert len(intervals) == score["pairs"]
            if all(w["whole_pair"] for w in intervals):
                assert score["pairs"] == 1
                if old[score["identity"]]["pairs"] > 1:
                    witnesses.append({"heading": score["heading_path"], "old_pairs": old[score["identity"]]["pairs"],
                                      "new_pairs": score["pairs"]})
            if score["body_tokens"] > fixed["receipt"]["maximum_sequence_length"]:
                long_units.append(score["identity"])
                assert not any(w["whole_pair"] for w in intervals)
            for side, total in (("body", score["body_tokens"]), ("ancestor", score["ancestor_tokens"]),
                                ("query", fixed["receipt"]["query_tokens"][0])):
                end = 0
                for a, b in sorted({tuple(w[side]) for w in intervals}):
                    assert 0 <= a <= end and a <= b <= total
                    end = max(end, b)
                assert end == total
        assert witnesses and long_units
        identity_fields = ("path_or_url", "snippet", "line_start", "line_end", "scope", "content_sha256")
        projected = {v: [tuple(r.get(k) for k in identity_fields) for r in packets[v]["sources"]]
                     for v in (WINDOW_RECIPE, FIT_WINDOW_RECIPE)}
        assert projected[WINDOW_RECIPE] == projected[FIT_WINDOW_RECIPE]
        return {"status": "PASS", "boundary": "in-process public prepare/query; diagnostic keep-all, not semantic acceptance",
                "public_prepares": 1, "public_queries": 2, "fit_witnesses": witnesses,
                "long_units": long_units, "source_hashes": before_sources, "logical_db_sha256": before_db,
                "receipts": {r: value["receipt"] for r, value in results.items()}}
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_probe(model_dir: Path, work_dir: Path | None = None) -> dict:
    captured, expired = [], []

    def observe(frame, event, value):
        if (event != "return" or frame.f_code.co_name != "project_native_rank_context"
                or not value):
            return
        payload, snapshot = value
        retrieval = frame.f_locals["retrieval"]
        structure = build_units(payload, snapshot, retrieval)
        assert not any(unit.body.strip().startswith("### Selected") for unit in structure.units)
        chosen = [unit.identity for unit in structure.units
                  if structure.metadata[unit.identity]["heading_path"][-1:] == ["Selected"]]
        assert len(chosen) == 1, structure.metadata
        rows, bound, receipt = close_selection(structure, chosen, payload, snapshot, retrieval)
        text = "".join(row["snippet"] for row in rows)
        for fact in (
            "Scope introduction.", "## Empty", "Tail condition stays.", "Limit condition",
            "Footnote condition.", "Continued footnote.", "Remote condition", "Other introduction.",
        ):
            assert fact in text, (fact, text)
        assert "Unselected noise." not in text
        assert receipt["incomplete_dependencies"][0]["target"] == "private.md#hidden", receipt
        for row in rows:
            entry = bound[row["evidence_id"]]
            ref = entry["source"]["_reference_evidence"]
            assert row["snippet"] == ref["raw_document"][ref["char_start"]:ref["char_end"]]
            assert hashlib.sha256(ref["raw_document"].encode()).hexdigest() == ref["source"]["content_sha256"]
            assert recheck_structural_row(row, entry, retrieval)["status"] == "complete"
        expired.append((rows[0], bound[rows[0]["evidence_id"]], retrieval))
        captured.append(receipt)

    settings = {
        "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "1",
        "DOCATLAS_EXPERIMENT_MINI_PATH": str(model_dir.expanduser().resolve()),
    }
    previous = {name: os.environ.get(name) for name in settings}
    try:
        with TemporaryDirectory(prefix="step10-structure-", dir=work_dir) as work:
            root = Path(work)
            project = root / "project"
            write_project(project, DOCUMENTS)
            with isolated_service(root / "state") as (service, config):
                index_project(service, config, project)
                os.environ.update(settings)
                database = Path(config.index.db_path)
                before = hashlib.sha256(database.read_bytes()).hexdigest()
                previous_profile = sys.getprofile()
                sys.setprofile(observe)
                try:
                    result = call_docs_tool_payload("get_docs_context", {
                        "question": QUESTION, "project_path": str(project), "scope": "project",
                    }, service)
                finally:
                    sys.setprofile(previous_profile)
                assert captured, result
                try:
                    recheck_structural_row(*expired[0])
                except StructuralContextError:
                    pass
                else:
                    raise AssertionError("Expired same-call source provenance accepted")
                assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        return {"status": "PASS", "boundary": BOUNDARY, "receipts": captured}
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path,
                        help="Existing pinned multilingual MiniLM assets; no download")
    parser.add_argument("--work-dir", type=Path,
                        help="Existing parent for isolated temporary project/state")
    parser.add_argument("--output", type=Path, help="Optional JSON receipt destination")
    parser.add_argument("--fit-correction", action="store_true",
                        help="Public final-delivery V1/V4 correction probe; work-dir must be new")
    parser.add_argument("--observer-parity", action="store_true",
                        help="With --fit-correction, only V4 OFF/ON; never reruns V1")
    args = parser.parse_args()
    if args.fit_correction and args.work_dir is None:
        parser.error("--fit-correction requires a new --work-dir")
    if args.observer_parity and not args.fit_correction:
        parser.error("--observer-parity requires --fit-correction")
    receipt = (run_fit_correction(args.model_dir, args.work_dir, observer_parity=args.observer_parity) if args.fit_correction
               else run_probe(args.model_dir, args.work_dir))
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
