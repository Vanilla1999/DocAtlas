"""Known-span feasibility, Q36 discovery injection, and Q15 locator-choice probes.

These are post-hoc upper bounds, not autonomous query planning or live-agent tests.
Run with no_network.py, --run pointing to run.py output and --fixture to the audit.
"""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import fields, replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import patch

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application._project_docs_service_part03 import _tag_retrieval_query
from docmancer.docs.application.model_visible_projection import _docs_source, _snapshot_entry, canonical_projection_bytes
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.interfaces.grounded_mcp_session import GroundedMCPSession
from docmancer.mcp.docs_server import call_docs_tool_payload
from eval.evidence_quality_v2.run import audit_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    cli = parser.parse_args()
    root, out = Path.cwd(), cli.run
    protocol = json.loads((out / "protocol.json").read_text())
    count = lambda payload: projection_token_count(canonical_projection_bytes(payload))
    norm = lambda text: " ".join(text.split()).casefold()
    result = {"method": __doc__, "feasibility": [], "q36_injection": [], "q15_reader": []}

    # This deliberately chooses an answer from gold. It only tests whether a
    # real complete span can fit the public DTO, not whether retrieval finds it.
    with sqlite3.connect(out / "index.db") as db:
        db.row_factory = sqlite3.Row
        for spec in protocol["hypotheses"]:
            matches = [dict(row) for row in db.execute("SELECT * FROM retrieval_children WHERE source_path=?", (spec["target_path"],))
                       if norm(spec["marker"]) in norm(row["display_text"])]
            row = min(matches, key=lambda x: len(x["display_text"]))
            original = {"path": row["source_path"], "heading_path": row["anchor"], "content": row["display_text"],
                        "project_identity": row["project_identity"], "authority": row["authority"],
                        "doc_scope": row["doc_scope"], "line_start": row["line_start"], "line_end": row["line_end"]}
            public = _docs_source(original)
            public.update(project_identity=row["project_identity"], authority=row["authority"],
                          scope=row["doc_scope"], line_start=row["line_start"], line_end=row["line_end"])
            snapshot = {public["evidence_id"]: _snapshot_entry(original, public)}
            payload = _payload([public], query_plan={"queries": [], "broad_context_only": True})
            result["feasibility"].append({"id": spec["id"], "payload": payload, "actual_tokens": count(payload),
                "audit_errors": audit_payload(payload, snapshot, root), "classification": "gold span DTO feasibility only"})

    # Borrow intrinsic source metadata from a real observed pack, never its
    # other question's query matches. Recompute every trace for Q36's own plan.
    base = json.load(gzip.open(out / "new40-Q36-baseline.json.gz", "rt"))["stages"]["projector_inputs"][-1]
    target, origin = None, None
    for path in sorted((cli.fixture / "traces").rglob("*.gz")):
        observed = json.load(gzip.open(path, "rt"))
        for inp in observed["stages"]["projector_inputs"]:
            target = next((deepcopy(x) for x in inp["context_pack"] if x.get("path") == "docs/source-continuation.md"
                           and "task-token savings" in x.get("content", "")), None)
            if target:
                origin = str(path)
                break
        if target:
            break
    assert target
    target.update(retrieval_query_matches={}, retrieval_query_ids=[], project_ranking={})
    chunk = RetrievedChunk(source=target["path"], chunk_index=0, text=target["content"], score=0,
                           metadata={**target, "project_doc_reason": target["catalog_role"]})
    for query in base["documentation_query_plan"]["queries"]:
        lookup = DocumentationLookup(**{f.name: query[f.name] for f in fields(DocumentationLookup) if f.name in query})
        chunk = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup,
                                     expected_project_identity=target["project_identity"])[0]
    target.update(retrieval_query_matches=chunk.metadata["retrieval_query_matches"],
                  retrieval_query_ids=chunk.metadata["retrieval_query_ids"])

    def oracle(probe, **kwargs):
        answer = qualify_evidence(probe, **kwargs)
        public_query = kwargs["query_id"] == "query-original" or kwargs["query_id"].startswith("query-lookup-")
        if (public_query and "task-token savings" in kwargs.get("evidence_text", "") and answer.reason == "insufficient_visible_match"
                and not answer.trace.get("missing_exact_terms") and not answer.trace.get("missing_parent_exact_terms")):
            trace = {**answer.trace, "qualified": True, "qualification_reason": "TEST_ONLY_known_support"}
            return replace(answer, qualified=True, covered_query_ids=(kwargs["query_id"],), coverage_kind="direct",
                           reason=trace["qualification_reason"], trace=trace)
        return answer

    for semantic in (False, True):
        replay = deepcopy(base)
        replay["context_pack"].append(deepcopy(target))
        with patch.object(projection, "qualify_evidence", oracle if semantic else qualify_evidence):
            payload, snapshot = projection.project_docs_context(retrieval=replay)
        result["q36_injection"].append({"semantic_oracle": semantic, "payload": payload,
            "actual_tokens": count(payload), "audit_errors": audit_payload(payload, snapshot, root),
            "target_origin": origin, "fresh_query_matches": target["retrieval_query_matches"],
            "marker_visible": any("task-token savings" in x["snippet"] for x in payload.get("sources", []))})

    os.environ.update(DOCATLAS_HOME=str(out / "reader-home"), DOCATLAS_AUTO_VECTORS="0", DOCATLAS_OFFLINE="1")
    config = DocmancerConfig.from_yaml(root / "docatlas.yaml")
    config.index.db_path, config.index.extracted_dir = str(out / "index.db"), str(out / "extracted")
    service = LibraryDocsService(config=config, config_source="explicit", registry=LibraryRegistry(config.index.db_path),
                                 agent=DocmancerAgent(config=config), job_tracker=DocsJobTracker())

    class Client:
        async def call_tool(self, name, args):
            return {"structuredContent": call_docs_tool_payload(name, args, service)}

        async def read_resource(self, uri):
            return {"contents": [{"text": json.dumps(service.source_reader.read(uri))}]}

    async def reader_probes():
        args = next(x["arguments"] for x in json.loads((out / "results.json").read_text())
                    if x["id"] == "Q15" and x["treatment"] == "baseline")
        for choice in ("docs/source-continuation.md", "docs/grounded-host-session.md"):
            host = await GroundedMCPSession.start(Client(), arguments=args, requested_facts={"decision": args["question"]})
            source = next(s for s in host.context["sources"] if s["path_or_url"] == choice and s.get("source_uri"))
            uri, reads = source["source_uri"], []
            for _ in range(2):
                read = await host.read(uri, missing_fact_id="decision")
                reads.append({"result": read, "actual_tokens": count(read)})
                if "does not cause I/O" in read.get("snippet", ""):
                    # Post-hoc human judgment of a verbatim rule, not a model.
                    host.support("decision", evidence_id=f"read-{len(reads)}", quote=read["snippet"])
                    break
                if not read.get("continuation"):
                    break
                uri = read["continuation"]
            result["q15_reader"].append({"locator_choice": choice, "initial": host.context,
                "initial_tokens": count(host.context), "reads": reads, "handoff": host.finish(),
                "method": "Separate question sessions; each limited to two reads. Manual locator choice and sufficiency judgment."})
    asyncio.run(reader_probes())
    result["protocol_sha256"] = hashlib.sha256((out / "protocol.json").read_bytes()).hexdigest()
    (out / "addenda.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    print("feasibility", [(x["id"], x["actual_tokens"], x["audit_errors"]) for x in result["feasibility"]])
    print("injection", [(x["semantic_oracle"], x["marker_visible"], x["audit_errors"]) for x in result["q36_injection"]])
    print("reader", [(x["locator_choice"], len(x["reads"]), x["handoff"]["status"]) for x in result["q15_reader"]])


if __name__ == "__main__":
    main()
