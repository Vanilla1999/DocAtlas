"""Bounded public-API preparation / frozen lexical comparison. No model calls."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT.parent / "step10-multidoc-gate/projects/validation/meridian"
PROJECT = "step10-index-descriptions-meridian"
NAMES = {"architecture.md", "calendar.md", "clock.md", "overview.md", "reservations.md", "weather.md"}
POLICY = {"mode": "lexical", "limit": 5, "budget": 4096, "expand": "none"}
QUERY_SHA = "ebdc87730508fe47d82cdcd978dff1ac768f443f0c20667417e09e0640f7346f"
SOURCE_ARTIFACT_SHA = "b9a690edba4f6186074ff4cccaddf5ed1acf1d439936e327e2c36fb8ad7f4b57"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sources() -> dict[str, str]:
    paths = sorted(SOURCES.glob("*.md"))  # Never traverse modules/.
    if {path.name for path in paths} != NAMES:
        raise ValueError("Meridian top-level source inventory changed")
    return {path.name: path.read_bytes().decode("utf-8") for path in paths}


def filters(version: str) -> dict:
    return {"project_identity": PROJECT, "doc_scope": "project",
            "source_class": "project_file", "resolved_version": version}


def snapshot_identity(texts: dict) -> dict:
    mapping = {name: digest(text.encode("utf-8")) for name, text in texts.items()}
    canonical = json.dumps(mapping, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sha = digest(canonical.encode("utf-8"))
    return {"source_hashes": mapping, "canonical_json": canonical, "sha256": sha,
            "resolved_version": "meridian-source-sha256:" + sha,
            "meaning": "corpus snapshot identity, not published library version"}


def agent_at(directory: Path):
    # Set before importing product code. All storage lives in a fresh run tree.
    directory.mkdir(parents=True, exist_ok=False)
    os.environ["DOCATLAS_HOME"] = str(directory / "home")
    os.environ["DOCATLAS_AUTO_VECTORS"] = "0"
    os.environ["DOCATLAS_EXPERIMENT_ACQUISITION"] = "v0"
    os.environ["DOCATLAS_EXPERIMENT_ACQUISITION_SECTIONS"] = "0"
    os.environ["DOCATLAS_EXPERIMENT_ACQUISITION_TERMS"] = "word"
    os.environ["DOCATLAS_EXPERIMENT_ACQUISITION_E5"] = "0"
    from docmancer.agent import DocmancerAgent
    from docmancer.core.config import DocmancerConfig
    config = DocmancerConfig()
    config.index.db_path = str(directory / "index.db")
    config.index.extracted_dir = str(directory / "extracted")
    config.embeddings.cache = str(directory / "embeddings-unused")
    config.retrieval.default_mode = "lexical"
    config.retrieval.max_sections_per_source = None
    return DocmancerAgent(config=config)


def ingest(agent, texts: dict, version: str, artifacts: dict | None = None):
    from docmancer.core.models import Document
    documents = []
    for source, content in texts.items():
        metadata = {**filters(version), "source_path": source, "format": "markdown",
                    "docs_snapshot_exact": True}
        if artifacts is not None:
            metadata["experimental_search_descriptions_v1"] = artifacts[source]
        documents.append(Document(source=source, content=content, metadata=metadata))
    agent.ingest_documents(documents, with_vectors=False)


def child_packet(agent) -> list:
    rows = agent.store.list_sections_for_embedding()
    hydrated = agent.store.fetch_sections_by_id([row["section_id"] for row in rows], budget=1_000_000)
    if len(hydrated) != len(rows):
        raise ValueError("child packet incomplete")
    return [{**row, "metadata": chunk.metadata} for row, chunk in zip(rows, hydrated)]


def prepare(args) -> None:
    texts = sources()
    snapshot = snapshot_identity(texts)
    if args.snapshot_version != snapshot["resolved_version"]:
        raise ValueError("snapshot version differs from canonical corpus identity")
    args.work.mkdir(parents=True, exist_ok=False)
    write(args.work / "prepare-freeze.json", {
        "command": sys.argv, "executable": sys.executable,
        "snapshot_version": args.snapshot_version,
        "snapshot_identity": snapshot,
        "sources": {name: digest(text.encode()) for name, text in texts.items()},
        "source_artifact_sha256": digest((ROOT / "source-only-descriptions.json").read_bytes()),
        "code_sha256": code_hashes(),
    })
    agent = agent_at(args.work / "index")
    ingest(agent, texts, args.snapshot_version)
    packet = {"schema": "source-only-child-packet-v1", "snapshot_version": args.snapshot_version,
              "snapshot_identity": snapshot,
              "filters": filters(args.snapshot_version),
              "documents": [{"source": source, "source_sha256": digest(text.encode()),
                             "content": text} for source, text in texts.items()],
              "children": child_packet(agent)}
    write(args.work / "children.json", packet)
    provenance(args.work)


def provenance(directory: Path) -> None:
    import docmancer
    write(directory / "runtime-provenance.json", {
        "command": sys.argv, "executable": sys.executable, "python": sys.version,
        "platform": platform.platform(), "package_file": docmancer.__file__,
        "boundary": "local public Python API; checkout, not installed stdio",
        "models_called": 0, "vectors_requested": False,
    })


def code_hashes() -> dict:
    repository = ROOT.parents[2]
    paths = [Path(__file__), repository / "tests/test_contextual_indexing.py",
             *sorted((repository / "docmancer").rglob("*.py"))]
    return {str(path.relative_to(repository)): digest(path.read_bytes()) for path in paths}


def adapt(args) -> None:
    """No product execution; reject heading/child differences for parent decision."""
    original = json.loads(args.source_artifact.read_text())
    if digest(args.source_artifact.read_bytes()) != SOURCE_ARTIFACT_SHA:
        raise ValueError("parent frozen source-only artifact changed")
    packet = json.loads(args.packet.read_text())
    texts = sources()
    if original.get("generation_mode") != "harness_subagent" or original.get("language") != "en":
        raise ValueError("unexpected source-only generation provenance")
    docs = original["documents"]
    if len(docs) != 6 or {doc["source"] for doc in docs} != NAMES:
        raise ValueError("description source inventory mismatch")
    packet_docs = packet["documents"]
    if len(packet_docs) != 6 or {doc["source"] for doc in packet_docs} != NAMES:
        raise ValueError("packet source inventory mismatch")
    for doc in packet_docs:
        if doc["content"] != texts[doc["source"]] or doc["source_sha256"] != digest(doc["content"].encode()):
            raise ValueError("packet source changed")
    artifacts = {}
    for doc in docs:
        source = doc["source"]
        if digest(texts[source].encode()) != doc["source_sha256"]:
            raise ValueError("source-only artifact is stale")
        children = {(r["char_start"], r["char_end"]): r for r in packet["children"] if r["source"] == source}
        records = []
        seen = set()
        for record in doc["records"]:
            span = (record["char_start"], record["char_end"])
            if span in seen or span not in children:
                raise ValueError(f"PARENT DECISION REQUIRED: heading != exact child or duplicate: {source}:{span}")
            seen.add(span)
            child = children[span]
            if digest(child["display_text"].encode()) != record["display_sha256"]:
                raise ValueError("child display hash mismatch")
            if digest(record["description"].encode()) != record["description_sha256"]:
                raise ValueError("description hash mismatch")
            records.append({key: value for key, value in record.items() if key != "heading"})
        if seen != set(children):
            raise ValueError(f"PARENT DECISION REQUIRED: incomplete exact child coverage: {source}")
        artifacts[source] = {"source_path": source, "source_sha256": doc["source_sha256"],
                             "context_sha256": doc["source_sha256"], "recipe": original["recipe"],
                             "version": "1", "model": original["model"],
                             "model_revision": original["model_revision"], "records": records}
    write(args.output, {"schema": "index-description-input-bundle-v1",
                        "source_artifact_sha256": digest(args.source_artifact.read_bytes()),
                        "packet_sha256": digest(args.packet.read_bytes()),
                        "snapshot_version": packet["snapshot_version"], "documents": artifacts})


def freeze(args) -> None:
    if digest(args.queries.read_bytes()) != QUERY_SHA:
        raise ValueError("parent frozen queries changed")
    bundle = json.loads(args.descriptions.read_text())
    if bundle["source_artifact_sha256"] != SOURCE_ARTIFACT_SHA:
        raise ValueError("description bundle provenance changed")
    texts = sources()
    write(args.manifest, {"schema": "index-description-freeze-v1", "policy": POLICY,
                         "snapshot_identity": snapshot_identity(texts),
                         "routing_recipe": "source-description-routing-v1",
                         "public_boundary": "all returned acquisition candidates; not final answer",
                         "limit_budget_args": "reported_not_applied by lexical dispatcher",
                         "snapshot_version": bundle["snapshot_version"],
                         "filters": filters(bundle["snapshot_version"]),
                         "queries_sha256": digest(args.queries.read_bytes()),
                         "descriptions_sha256": digest(args.descriptions.read_bytes()),
                         "source_artifact_sha256": SOURCE_ARTIFACT_SHA,
                         "runner_sha256": digest(Path(__file__).read_bytes()),
                         "code_sha256": code_hashes(),
                         "sources": {name: digest(text.encode()) for name, text in texts.items()}})


def run(args) -> None:
    manifest = json.loads(args.manifest.read_text())
    texts = sources()
    if (manifest["queries_sha256"] != digest(args.queries.read_bytes())
            or manifest["queries_sha256"] != QUERY_SHA
            or manifest["descriptions_sha256"] != digest(args.descriptions.read_bytes())
            or manifest["source_artifact_sha256"] != SOURCE_ARTIFACT_SHA
            or digest((ROOT / "source-only-descriptions.json").read_bytes()) != SOURCE_ARTIFACT_SHA
            or manifest["runner_sha256"] != digest(Path(__file__).read_bytes())
            or manifest["code_sha256"] != code_hashes()
            or manifest["sources"] != {name: digest(text.encode()) for name, text in texts.items()}
            or manifest["snapshot_identity"] != snapshot_identity(texts)
            or manifest["snapshot_version"] != snapshot_identity(texts)["resolved_version"]
            or manifest["policy"] != POLICY
            or manifest["filters"] != filters(manifest["snapshot_version"])):
        raise ValueError("frozen inputs changed")
    queries = json.loads(args.queries.read_text())
    if queries["policy"] != POLICY:
        raise ValueError("query policy changed")
    bundle = json.loads(args.descriptions.read_text())
    if bundle["snapshot_version"] != manifest["snapshot_version"] or set(bundle["documents"]) != NAMES:
        raise ValueError("description bundle scope mismatch")
    args.work.mkdir(parents=True, exist_ok=False)
    write(args.work / "frozen-inputs.json", manifest)
    for arm in ("baseline", "descriptions"):
        agent = agent_at(args.work / arm)
        from docmancer.retrieval.runtime import dispatcher_for_agent
        from docmancer.retrieval.experimental_acquisition import (
            ACQUISITION_CANDIDATES, ACQUISITION_ESTIMATED_TOKENS, ACQUISITION_TEXT_BYTES,
        )
        provenance(args.work / arm)
        started = time.monotonic()
        ingest(agent, texts, manifest["snapshot_version"], bundle["documents"] if arm == "descriptions" else None)
        write(args.work / arm / "index.json", {"prepare_seconds": time.monotonic() - started,
                                              "children": child_packet(agent)})
        dispatcher = dispatcher_for_agent(agent, mode="lexical")
        results = []
        for query in queries["queries"]:
            started = time.monotonic()
            result = dispatcher.run(query["question"], filters=manifest["filters"], **POLICY)
            raw = asdict(result)
            raw["chunks"] = [chunk.model_dump(mode="json") for chunk in result.chunks]
            # Preserve raw before grading; only delivered source text proves facts.
            write(args.work / arm / f"{query['id']}.raw.json", raw)
            packet_bytes = len((args.work / arm / f"{query['id']}.raw.json").read_bytes())
            facts = [{**fact, "present": any(chunk.source == fact["source"] and fact["quote"] in chunk.text
                                            for chunk in result.chunks)} for fact in query["facts"]]
            fidelity = True
            for chunk in result.chunks:
                metadata = chunk.metadata
                span = metadata.get("char_span", [])
                fidelity = fidelity and (
                    chunk.source in texts and len(span) == 2
                    and texts[chunk.source][span[0]:span[1]] == chunk.text
                    and metadata.get("content_hash") == digest(chunk.text.encode())
                    and metadata.get("source_content_hash") == digest(texts[chunk.source].encode())
                    and all(metadata.get(key) == value for key, value in manifest["filters"].items()))
            size = sum(len(chunk.text.encode("utf-8")) for chunk in result.chunks)
            results.append({"id": query["id"], "seconds": time.monotonic() - started,
                            "measurement_boundary": "all_public_returned_acquisition_candidates_not_final_answer",
                            "routing_recipe": "source-description-routing-v1",
                            "limit_budget_args": "reported_not_applied",
                            "returned_candidate_count": len(result.chunks),
                            "public_candidate_counts": result.candidate_counts,
                            "acquisition_ceilings_runtime_constants": {
                                "candidates": ACQUISITION_CANDIDATES,
                                "estimated_tokens": ACQUISITION_ESTIMATED_TOKENS,
                                "utf8_bytes": ACQUISITION_TEXT_BYTES},
                            "public_acquisition_traces": [chunk.metadata.get("acquisition") for chunk in result.chunks],
                            "internal_candidate_recall": None, "facts": facts,
                            "facts_present": sum(fact["present"] for fact in facts),
                            "facts_required": len(facts), "source_text_fidelity": fidelity,
                            "no_answer_expected": query["no_answer_expected"],
                            "empty_packet": not result.chunks, "returned_utf8_bytes": size,
                            "raw_packet_json_utf8_bytes": packet_bytes,
                            "description_metadata_client_visible": any(
                                "experimental_search_description_v1" in chunk.metadata for chunk in result.chunks),
                            "utf8_bytes_div4_ceiling_estimate": (size + 3) // 4,
                            "provider_tokens": None,
                            "annotation_harness_provider_costs": "unknown",
                            "empty_no_answer_is_not_semantic_success": True,
                            "complete": fidelity and all(fact["present"] for fact in facts)
                            and (not query["no_answer_expected"] or not result.chunks)})
        write(args.work / arm / "results.json", results)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--snapshot-version", required=True)
    p = commands.add_parser("adapt")
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--source-artifact", type=Path, default=ROOT / "source-only-descriptions.json")
    p.add_argument("--output", type=Path, default=ROOT / "descriptions.json")
    for command in ("freeze", "run"):
        p = commands.add_parser(command)
        p.add_argument("--queries", type=Path, default=ROOT / "queries.json")
        p.add_argument("--descriptions", type=Path, default=ROOT / "descriptions.json")
        p.add_argument("--manifest", type=Path, default=ROOT / "freeze.json")
        if command == "run":
            p.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    globals()[args.command](args)


if __name__ == "__main__":
    main()
