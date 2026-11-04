"""Fixed, non-semantic work ceilings for native lexical acquisition.

Chosen before runtime; see reports/docatlas-grounded-20261013/heuristic-removal/
A_ACQUISITION.md. These are not final context budgets or completeness guarantees.
"""
from __future__ import annotations

import os

ACQUISITION_CANDIDATES = 256
ACQUISITION_ESTIMATED_TOKENS = 131_072
ACQUISITION_TEXT_BYTES = 1_048_576
ACQUISITION_VARIANT = os.environ.get("DOCATLAS_EXPERIMENT_ACQUISITION", "v0").strip().lower()
if ACQUISITION_VARIANT not in {"v0", "v5"}:
    raise ValueError("DOCATLAS_EXPERIMENT_ACQUISITION must be v0 or v5")
ACQUISITION_METHOD = (
    "fts5_source_bm25_heading_concat_v5" if ACQUISITION_VARIANT == "v5"
    else "fts5_source_bm25_or_v2"
)
