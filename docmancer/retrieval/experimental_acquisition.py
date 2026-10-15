"""Fixed, non-semantic work ceilings for native lexical acquisition.

Chosen before runtime; see reports/docatlas-grounded-20261013/heuristic-removal/
A_ACQUISITION.md. These are not final context budgets or completeness guarantees.
"""
from __future__ import annotations

ACQUISITION_CANDIDATES = 256
ACQUISITION_ESTIMATED_TOKENS = 131_072
ACQUISITION_TEXT_BYTES = 1_048_576
ACQUISITION_METHOD = "fts5_bm25_equal_fields_or_v1"
