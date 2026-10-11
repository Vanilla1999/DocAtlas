"""Real SQLite-backed CLI reads; lifecycle diagnostics must preserve delivery."""

import json
import os
import subprocess
import sys

import yaml

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document


def test_cli_trace_off_on_off_preserves_lexical_fact_and_json(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    source = "docs/auth.md"
    fact = "Authenticate with OAuth tokens."
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(source=source, content="# Auth\n\n" + fact, metadata={"format": "markdown"})],
        recreate=True,
        with_vectors=False,
    )
    config_path = tmp_path / "docmancer.yaml"
    config_path.write_text(yaml.safe_dump(config.model_dump()), encoding="utf-8")
    env = dict(os.environ, DOCATLAS_TRACE="1", DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0")
    results = []
    # Both OFF invocations must override the enabled host environment.
    for flag in ("--no-trace", "--trace", "--no-trace"):
        child = subprocess.run(
            [sys.executable, "-m", "docmancer.cli", flag, "--config", str(config_path),
             "query", "OAuth tokens", "--mode", "lexical", "--format", "json"],
            env=env, text=True, capture_output=True, timeout=60, check=True,
        )
        payload = json.loads(child.stdout)
        assert payload["query"] == "OAuth tokens"
        assert payload["mode_used"] == "lexical"
        assert payload["degraded"] is False and payload["failures"] == {}
        assert payload["results"]
        assert {chunk["source"] for chunk in payload["results"]} == {source}
        assert fact in "\n".join(chunk["text"] for chunk in payload["results"])
        events = [json.loads(line) for line in child.stderr.splitlines() if line.startswith("{")]
        events = [event for event in events if event.get("event", "").startswith("docatlas_")]
        if flag == "--no-trace":
            assert events == []
        else:
            assert [event["event"] for event in events] == [
                "docatlas_request_start", "docatlas_request_end",
            ]
            start, end = events
            assert start["request_id"] and start["request_id"] == end["request_id"]
            assert all(event["interface"] == "cli" and event["operation"] == "query" for event in events)
            assert start["status"] == "started" and end["status"] == "success"
            assert end["duration_ms"] >= 0 and end["trace_incomplete"] is False
            assert fact not in json.dumps(events) and str(config_path) not in json.dumps(events)
        results.append(child)
    assert results[0].stdout == results[1].stdout == results[2].stdout
