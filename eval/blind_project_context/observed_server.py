"""Start the real DocAtlas stdio MCP docs server with passive observers.

run.py starts this file instead of ``doc-atlas mcp docs-serve`` so that it can
report, per question, whether internal ceilings were reached. docmancer is
imported from PYTHONPATH (the source tree under test). When
``BLIND_OBSERVER_LOG`` is set, two existing methods are wrapped; each wrapper
calls the original, appends one JSON line and returns the original object:

* ``SQLiteStore.acquire_candidates``: the counters the store already attaches
  to every candidate (SQL rows before the 256-candidate ceiling, admitted rows,
  rows skipped by the token/byte ceilings) and, when ``BLIND_OBSERVER_FACTS``
  names a JSON list of ``{"fact_id", "quote"}``, the rank of the first
  returned candidate whose text contains each quote, so a missed fact can be
  told apart: never acquired, or acquired and dropped later;
* ``ProjectMetadataReader.read``: catalogued candidates and any wall-clock or
  byte truncation warning of document discovery.

Without the variable nothing is wrapped. run.py --no-observer exists to show
that delivered context is identical either way.
"""
from __future__ import annotations

import json
import os
import sys

if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    sys.path.pop(0)

LOG = os.environ.get("BLIND_OBSERVER_LOG")
FACTS = os.environ.get("BLIND_OBSERVER_FACTS")


def _append(event: dict) -> None:
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _install() -> None:
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.project import ProjectMetadataReader

    acquire = SQLiteStore.acquire_candidates
    read = ProjectMetadataReader.read
    facts = {}
    if FACTS:
        with open(FACTS, encoding="utf-8") as handle:
            facts = {item["fact_id"]: item["quote"] for item in json.load(handle)}

    def observed_acquire(self, text, *args, **kwargs):
        chunks = acquire(self, text, *args, **kwargs)
        counters = dict((chunks[0].metadata or {}).get("acquisition") or {}) if chunks else {}
        ranks = {}
        for rank, chunk in enumerate(chunks, start=1):
            body = chunk.text or ""
            for fact_id, quote in facts.items():
                if fact_id not in ranks and quote in body:
                    ranks[fact_id] = rank
        _append({"event": "acquisition", "text": text, "expand": kwargs.get("expand"),
                 "filters": kwargs.get("filters"), "returned_rows": len(chunks), "fact_ranks": ranks,
                 **counters})
        return chunks

    def observed_read(self, project_path, *args, **kwargs):
        metadata = read(self, project_path, *args, **kwargs)
        _append({"event": "catalog_read", "candidates": len(metadata.docs_candidates),
                 "truncation_warnings": [w for w in metadata.warnings if "truncated" in w]})
        return metadata

    SQLiteStore.acquire_candidates = observed_acquire
    ProjectMetadataReader.read = observed_read


if LOG:
    _install()

from docmancer.cli.__main__ import cli  # noqa: E402

sys.argv = ["doc-atlas", "mcp", "docs-serve"]
cli()
