"""Opt-in real Qdrant/FastEmbed integration. No replacement components.

Run explicitly with a downloaded Qdrant binary and an isolated model cache.
This is retrieval-runtime integration, not MCP/stdio or a relevance benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qdrant-binary", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="docatlas-real-hybrid-") as temporary:
        root = Path(temporary)
        home = root / "home"
        home.mkdir(mode=0o700)
        os.environ.update({
            "DOCATLAS_HOME": str(home), "DOCATLAS_FASTEMBED_CACHE_DIR": str(args.model_cache.resolve()),
            "HF_HOME": str(args.model_cache.resolve() / "hf-home"),
            "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false",
        })
        from docmancer.agent import DocmancerAgent
        from docmancer.core.config import DocmancerConfig, VectorStoreConfig
        from docmancer.core.models import Document
        from docmancer.core.product_identity import ensure_owned_home
        from docmancer.retrieval.runtime import dispatcher_for_agent
        from eval.heuristic_removal.receipts import database

        ensure_owned_home(home)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        config_file = root / "qdrant.yaml"
        server_config = {
            "storage": {"storage_path": str(root / "storage"), "snapshots_path": str(root / "snapshots"),
                        "performance": {"max_search_threads": 2, "optimizer_cpu_budget": 1}},
            "service": {"host": "127.0.0.1", "http_port": port, "grpc_port": None, "max_workers": 2},
            "cluster": {"enabled": False}, "telemetry_disabled": True,
        }
        config_file.write_text(yaml.safe_dump(server_config))
        server_env = {**os.environ, "QDRANT__SERVICE__HOST": "127.0.0.1",
                      "QDRANT__SERVICE__HTTP_PORT": str(port),
                      "QDRANT__STORAGE__STORAGE_PATH": str(root / "storage"),
                      "QDRANT__STORAGE__SNAPSHOTS_PATH": str(root / "snapshots"),
                      "QDRANT__TELEMETRY_DISABLED": "true"}
        with (args.output / "qdrant.log").open("w") as log:
            process = subprocess.Popen([str(args.qdrant_binary.resolve()), "--config-path", str(config_file)],
                                       cwd=root, env=server_env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Qdrant exited before readiness; see qdrant.log")
                    try:
                        with urllib.request.urlopen(url + "/readyz", timeout=1) as response:
                            assert response.status == 200
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.1)
                config = DocmancerConfig()
                config.index.db_path = str(root / "docs.db")
                config.index.extracted_dir = str(root / "extracted")
                config.embeddings.provider = "fastembed"
                config.embeddings.model = "BAAI/bge-small-en-v1.5"
                config.embeddings.dimensions = 384
                config.embeddings.sparse_model = "Qdrant/bm25"
                config.embeddings.cache = str(root / "embedding-cache")
                config.vector_store = VectorStoreConfig(provider="qdrant", url=url)
                config.retrieval.default_mode = "hybrid"
                config.retrieval.max_sections_per_source = 1
                config.retrieval.hierarchical.enabled = True
                config.retrieval.hierarchical.auto_min_documents = 1
                source = ("# Observatory aperture\n\nObservatory aperture is 73 mm.\n\n"
                          "# Observatory shutter\n\nObservatory shutter waits 19 seconds.\n\n"
                          "# Observatory archive\n\nObservatory archive retains 41 nights.\n")
                agent = DocmancerAgent(config=config)
                agent.ingest_documents([
                    Document(source="observatory.md", content=source, metadata={"format": "markdown"}),
                    Document(source="secret.md", content="# Observatory\n\nObservatory secret is HIDDEN_97.\n",
                             metadata={"format": "markdown"}),
                ], with_vectors=True)
                before = database(config.index.db_path)
                dispatcher = dispatcher_for_agent(agent, mode="hybrid")

                def vector_snapshot():
                    request = urllib.request.Request(
                        url + f"/collections/{dispatcher.collection}/points/scroll",
                        data=json.dumps({"limit": 16, "with_payload": True, "with_vector": True}).encode(),
                        headers={"Content-Type": "application/json"}, method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=5) as response:
                        result = json.load(response)["result"]
                    assert result["next_page_offset"] is None
                    return sorted(result["points"], key=lambda point: str(point["id"]))

                vector_before = vector_snapshot()
                records = []
                for mode in ("sparse", "hybrid"):
                    result = dispatcher.run("observatory", mode=mode, limit=10, budget=4000,
                                            expand="none", filters={"forbidden_sources": ["secret.md"]})
                    record = {"mode": result.mode_used, "counts": result.candidate_counts,
                              "failures": result.failures, "contributions": result.contributions,
                              "chunks": [chunk.model_dump() for chunk in result.chunks]}
                    records.append(record)
                    (args.output / "retrieval.json").write_text(json.dumps(records, indent=2))
                    assert result.mode_used == mode and not result.failures, record
                    expected_lanes = {"sparse"} if mode == "sparse" else {"lexical", "dense", "sparse"}
                    assert set(result.candidate_counts) == expected_lanes, record
                    assert all(result.candidate_counts[lane] > 0 for lane in expected_lanes)
                    for fact in ("Observatory aperture is 73 mm.", "Observatory shutter waits 19 seconds.",
                                 "Observatory archive retains 41 nights."):
                        assert any(fact in chunk.text for chunk in result.chunks), record
                    for chunk in result.chunks:
                        assert chunk.source == "observatory.md" and chunk.text in source, record
                        assert "HIDDEN_97" not in chunk.text
                        metadata = chunk.metadata
                        assert metadata["content_hash"] == hashlib.sha256(chunk.text.encode()).hexdigest()
                        assert metadata["source_content_hash"] == hashlib.sha256(source.encode()).hexdigest()
                        start, end = metadata["char_span"]
                        assert source[start:end] == chunk.text
                        start, end = metadata["byte_span"]
                        assert source.encode()[start:end] == chunk.text.encode()
                    assert database(config.index.db_path) == before
                    assert vector_snapshot() == vector_before
                manifest = {"status": "PASS", "runtime_calls": 2, "mocks": False,
                            "dense_model": config.embeddings.model, "sparse_model": config.embeddings.sparse_model,
                            "binary_sha256": hashlib.sha256(args.qdrant_binary.read_bytes()).hexdigest(),
                            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                            "boundary": "production ingest and retrieval runtime, isolated Qdrant/FastEmbed"}
                (args.output / "RESULT.json").write_text(json.dumps(manifest, indent=2) + "\n")
                print(json.dumps(manifest))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
