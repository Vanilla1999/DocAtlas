"""Small offline intervention study; never imported by production.

Run through the audit's no_network.py wrapper. Requires the previous audit's
immutable SQLite fixture and environment.json; raw traces stay outside checkout.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.model_visible_projection import canonical_projection_bytes
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.run import audit_payload


def normalized(value):
    return " ".join(str(value).split()).casefold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe", choices=("initial", "soft_lexical", "oracle_only"), default="initial")
    cli = parser.parse_args()
    root, here = Path.cwd().resolve(), Path(__file__).resolve().parent
    protocol = json.loads((here / "protocol.json").read_text())
    out = cli.output.resolve()
    assert not out.is_relative_to(root) and not out.exists(), "Choose a fresh external output"
    out.mkdir(parents=True)
    environment = json.loads((cli.fixture / "environment.json").read_text())
    for item in environment["source_manifest"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    with sqlite3.connect(f"file:{cli.index.resolve()}?mode=ro", uri=True) as source:
        with sqlite3.connect(out / "index.db") as destination:
            source.backup(destination)
    os.environ.update(DOCATLAS_HOME=str(out / "home"), DOCATLAS_AUTO_VECTORS="0", DOCATLAS_OFFLINE="1")
    config = DocmancerConfig.from_yaml(root / "docatlas.yaml")
    config.index.db_path = str(out / "index.db")
    config.index.extracted_dir = str(out / "extracted")
    service = LibraryDocsService(config=config, config_source="explicit",
        registry=LibraryRegistry(config.index.db_path), agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker())
    cases = {
        sample: {c["id"]: c for c in json.loads((here.parent / filename).read_text())["cases"]}
        for sample, filename in (("new40", "followup_questions.json"), ("old40", "questions.json"))
    }
    previous = json.loads((here.parent / "continued_loss_retest.json").read_text())["samples"]
    rows, baselines = [], {}

    def save(name, value):
        data = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n").encode()
        (out / name).write_bytes(gzip.compress(data, mtime=0) if name.endswith(".gz") else data)

    def call(spec, treatment, *, oracle=False, priority=False, soft=False):
        sample, qid = spec.get("sample", "new40"), spec["id"]
        case = cases[sample][qid]
        args = {"question": case["question"], "project_path": str(root), "scope": "all",
                "lookup_queries": [spec["compact_lookup"]] if treatment == "compact" else case["host_lookups"]}
        marker = normalized(spec.get("marker", ""))
        interventions = []

        def semantic_oracle(probe, **kwargs):
            result = qualify_evidence(probe, **kwargs)
            candidate = kwargs.get("candidate") or {}
            path = candidate.get("path") or candidate.get("project_doc_path") or candidate.get("source_path")
            # Gold is used only here. Never override source policy or missing
            # exact anchors. A target marker is NOT a production support test.
            public_query = kwargs["query_id"] == "query-original" or kwargs["query_id"].startswith("query-lookup-")
            eligible = (bool(result.trace.get("body_matched_terms")) if soft else
                        public_query and path == spec.get("target_path") and marker
                        and marker in normalized(kwargs.get("evidence_text", "")))
            if (eligible
                    and result.reason == "insufficient_visible_match"
                    and not result.trace.get("missing_exact_terms")
                    and not result.trace.get("missing_parent_exact_terms")):
                trace = {**result.trace, "qualified": True,
                         "qualification_reason": "TEST_ONLY_nonzero_body_match" if soft else "TEST_ONLY_known_support"}
                interventions.append({"path": path, "query_id": kwargs["query_id"], "before": dict(result.trace)})
                return replace(result, qualified=True, covered_query_ids=(kwargs["query_id"],),
                               coverage_kind="direct", reason=trace["qualification_reason"], trace=trace)
            return result

        rank = projection._facet_aware_candidates

        def target_first(values, *args, **kwargs):
            ranked = rank(values, *args, **kwargs)
            return sorted(ranked, key=lambda x: not (
                (x.get("path_or_url") or x.get("path")) == spec.get("target_path")
                and marker in normalized(x.get("snippet", x.get("content", "")))))

        started = time.perf_counter()
        with ExitStack() as stack:
            if oracle:
                for module in list(sys.modules.values()):
                    if module and getattr(module, "__name__", "").startswith("docmancer."):
                        if getattr(module, "qualify_evidence", None) is qualify_evidence:
                            stack.enter_context(patch.object(module, "qualify_evidence", semantic_oracle))
            if priority:
                stack.enter_context(patch.object(projection, "_facet_aware_candidates", target_first))
            payload, trace = observe_call(service, args)
        name = f"{sample}-{qid}-{treatment}"
        save(name + ".json.gz", trace)
        row = {"sample": sample, "id": qid, "treatment": treatment, "arguments": args,
               "payload": payload, "actual_tokens": projection_token_count(canonical_projection_bytes(payload)),
               "audit_errors": audit_payload(payload, trace["snapshot"], root),
               "seconds": round(time.perf_counter() - started, 3), "trace": name + ".json.gz",
               "oracle_overrides": interventions,
               "marker_visible": bool(marker and any(marker in normalized(s.get("snippet", "")) for s in payload.get("sources", [])))}
        if treatment == "baseline":
            old = next(x for x in previous[sample]["rows"] if x["id"] == qid and x["lane"] == "guided")
            spans = lambda p: [(s["path_or_url"], s["snippet"]) for s in p.get("sources", [])]
            row["same_as_published_baseline"] = spans(old["payload"]) == spans(payload)
            assert row["same_as_published_baseline"], name
            row["previous_grade"] = old["human_evidence_sufficiency"]
            baselines[(sample, qid)] = deepcopy(payload)
        rows.append(row)
        save("results.json", rows)
        print(name, payload.get("kind"), row["actual_tokens"], "marker", row["marker_visible"],
              "errors", row["audit_errors"], flush=True)

    save("protocol.json", protocol)
    if cli.probe == "soft_lexical":
        save("soft_lexical_protocol.json", json.loads((here / "soft_lexical_protocol.json").read_text()))
    for spec in protocol["hypotheses"] + protocol["controls"]:
        if cli.probe == "oracle_only" and spec in protocol["controls"]:
            continue
        call(spec, "baseline")
        if cli.probe == "soft_lexical":
            call(spec, "soft_lexical", oracle=True, soft=True)
        elif cli.probe == "initial":
            call(spec, "compact")
    if cli.probe in {"initial", "oracle_only"}:
        for spec in protocol["hypotheses"]:
            call(spec, "target_first", priority=True)
            call(spec, "qualification_oracle", oracle=True)
            call(spec, "qualification_and_priority_oracle", oracle=True, priority=True)
    save("environment.json", {"protocol_sha256": hashlib.sha256((here / "protocol.json").read_bytes()).hexdigest(),
        "source_manifest": environment["source_manifest"], "indexed_documents": len(environment["source_manifest"]),
        "design": protocol["design"], "probe": cli.probe, "python": sys.version, "fixture": str(cli.fixture), "index": str(cli.index)})


if __name__ == "__main__":
    main()
