"""Real installed MCP + reversible host packing, paired on the SAME response.

Reuses the established SQLite/ONNX/stdin scenario and independent frozen oracles.
Packing controls use actual issued responses, never fabricated retrieval results.
No strong-model answer accuracy or full provider-cost claim is made.
"""
from __future__ import annotations
import argparse
import asyncio
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location(
    "preservation_scenario", Path(__file__).with_name("semantic_preservation_integration.py"))
pres = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pres)
base = pres.base
base.__file__ = __file__
SUITES = ("v40", "new16", "fresh8", "semantic12", "preservation8")
POLICIES = ("fixed", "facet-guarded-v1")
FORMATS = ("paths-v1", "sections-v1", "adaptive-v1")


def independent_expand(view):
    """Independent visible-field interpretation; not the product decoder."""
    if view["context_format"] == "docatlas.model-context.v1":
        return deepcopy(view)
    assert view["context_format"] == "docatlas.packed-model-context.v1"
    rows = []
    for row in view["sources"]:
        meta = view["source_catalog"][row["source"]]
        fields = {k: deepcopy(v) for k, v in row.items() if k not in {"source", "lines"}}
        assert not set(fields).intersection(meta), "catalog shadows a source field"
        fields.update(deepcopy(meta))
        if "lines" in row:
            assert len(row["lines"]) == 2
            assert "line_start" not in fields and "line_end" not in fields
            fields["line_start"], fields["line_end"] = row["lines"]
        rows.append(fields)
    result = {k: deepcopy(v) for k, v in view.items()
              if k not in {"source_catalog", "packing_notice", "packing_policy", "sources"}}
    result["sources"] = rows
    result["context_format"] = "docatlas.model-context.v1"
    return result


def evaluate_packing(args, records):
    import tiktoken
    from docmancer.docs.application.model_context_view import canonical
    from docmancer.docs.interfaces.host_context import extract_tool_payload
    from docmancer.docs.application.model_context_packing import (
        prepare_packed_context, restore_packed_result, resolve_packed_reference,
    )
    enc = tiktoken.get_encoding("o200k_base")
    results, controls, previous_meta = [], [], None
    for record in records:
        assert not record["runtime_error"] and record["integrity"]
        path = args.out / record["family"] / (record["case_id"] + "-response.json")
        raw = json.loads(path.read_text())
        original_wire = raw["content"][0]["text"]
        original = json.loads(original_wire)
        assert original_wire == canonical(original)
        original_packet = extract_tool_payload(raw)
        fingerprint = canonical(raw)
        before_tokens = len(enc.encode(original_wire, disallowed_special=()))
        before_bytes = len(original_wire.encode())
        all_views = {}
        for policy in FORMATS:
            begin = time.perf_counter()
            view, metadata = prepare_packed_context(raw, policy=policy)
            host_seconds = time.perf_counter() - begin
            assert independent_expand(view) == original, "visible evidence/decisions changed"
            assert restore_packed_result(view, metadata) == original_packet
            for source in original["sources"]:
                ref = source["ref"]
                restored = resolve_packed_reference(view, metadata, ref)
                assert restored["snippet"] == source["text"]
                assert restored["path_or_url"] == source["path"]
                for key in ("line_start", "line_end", "section"):
                    if key in source:
                        assert restored[key] == source[key]
            text = canonical(view)
            tokens = len(enc.encode(text, disallowed_special=()))
            size = len(text.encode())
            if policy == "adaptive-v1":
                assert tokens <= before_tokens and size <= before_bytes
            base.save(args.out / "packed" / policy / (record["case_id"] + ".json"), view)
            results.append({"suite": args.suite, "selection": args.policy,
                "case_id": record["case_id"], "packing": policy,
                "actual_format": view["context_format"],
                "actual_policy": view.get("packing_policy", "original-v1"),
                "tokens": tokens, "baseline_tokens": before_tokens,
                "bytes": size, "baseline_bytes": before_bytes,
                "host_seconds": host_seconds, "same_response_packet": True,
                "same_full_citation_refs": True, "visible_fields_identical_after_expansion": True,
                "source_count": len(original["sources"]),
                "documented_witness_groups": sum(c["covered"] for c in record["claims"])})
            all_views[policy] = (view, metadata)
        # Host negative controls start with an actual delivered view and ledger.
        view, metadata = all_views["sections-v1"]
        attacks = []
        for key in ("text", "ref"):
            bad = deepcopy(view); bad["sources"][0][key] += " forged"
            attacks.append((key, bad, metadata))
        bad = deepcopy(view)
        bad["source_catalog"][bad["sources"][0]["source"]]["path"] += ".foreign"
        attacks.append(("path", bad, metadata))
        bad = deepcopy(view); bad["sources"][0]["lines"] = [1, 1000000]
        attacks.append(("lines", bad, metadata))
        bad = deepcopy(view); bad["source_catalog"]["unused"] = {"path": "foreign"}
        attacks.append(("extra_catalog_record", bad, metadata))
        bad = deepcopy(view); bad["answer_supported"] = True
        attacks.append(("authority", bad, metadata))
        bad = deepcopy(view); bad["packing_policy"] = "unrecognized"
        attacks.append(("policy", bad, metadata))
        attacks.append(("missing_ledger", view, {}))
        if previous_meta is not None and canonical(previous_meta) != canonical(metadata):
            attacks.append(("cross_response_ledger", view, previous_meta))
        for name, bad, ledger in attacks:
            try:
                restore_packed_result(bad, ledger)
            except (ValueError, KeyError, TypeError):
                controls.append({"case_id": record["case_id"], "attack": name, "rejected": True})
            else:
                raise AssertionError("tampered host context accepted: " + name)
        try:
            resolve_packed_reference(view, metadata, "s1")
        except ValueError:
            controls.append({"case_id": record["case_id"], "attack": "unscoped_ref", "rejected": True})
        else:
            raise AssertionError("unscoped reference accepted")
        assert canonical(raw) == fingerprint, "host packing mutated original transport"
        previous_meta = metadata
    base.save(args.out / "PACKING.json", {"records": results, "controls": controls,
        "additional_retrieval_calls": 0, "additional_model_calls": 0,
        "provider_usage": None, "answer_generation_tested": False,
        "boundary": "installed host transforms actual public stdio responses; every packing arm shares its exact packet and nonce"})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "work", "out", "model", "qa-model"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--suite", choices=SUITES, required=True)
    p.add_argument("--policy", choices=POLICIES, required=True)
    p.add_argument("--worker", action="store_true"); p.add_argument("--family")
    args = p.parse_args()
    for name in ("repo", "work", "out", "model", "qa_model"):
        setattr(args, name, getattr(args, name).resolve())
    if args.worker:
        return base.worker(args)
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo), "non-editable installed package required"
    assert all(f.read_bytes() == (args.repo / "docmancer" / f.relative_to(origin)).read_bytes()
               for f in origin.rglob("*.py"))
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700); args.out.mkdir(parents=True)
    dirs = ("prepared_model_comparison40", "adaptive_gap_holdout", "fresh_dialogues/fixtures",
            "fresh_dialogues/oracle", "semantic_sufficiency_holdout", "semantic_preservation_holdout")
    hashes = {str(f.relative_to(args.repo)): base.digest(f.read_bytes()) for d in dirs
              for f in (args.repo / "eval" / d).rglob("*") if f.is_file() and "__pycache__" not in f.parts}
    base.save(args.out / "FREEZE.json", {"head": os.environ["TESTED_SHA"], "files": hashes})
    records = asyncio.run(base.client(args))
    if args.suite == "preservation8":
        pres.assess_new(args, records)
    else:
        base.assess(args, records)
    evaluate_packing(args, records)
    assert all(base.digest((args.repo / f).read_bytes()) == h for f, h in hashes.items())


if __name__ == "__main__":
    main()
