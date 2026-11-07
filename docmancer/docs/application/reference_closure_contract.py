"""Versioned closure experiment; the historical Qwen scoring input is unchanged."""
import hashlib
from . import context_evidence_scoring as scoring

RECIPE = "qwen3-contextual-addressed-section-closure-v3"
STRUCTURAL_RECIPE = "explicit_addressed_section_closure_v3"
CALIBRATION_RECIPE = "largest-finite-breakpoint-independent-reference-closure-v3"
CONTRACT = {
    "recipe": RECIPE, "structural_recipe": STRUCTURAL_RECIPE,
    "scoring_contract_sha256": scoring.CONTRACT_SHA256,
    "seeds": "own body plus ancestors; no seed subtree",
    "expand": "all delivered bodies, including ancestors and definition owners",
    "anchor": "unique owning section through next heading of same or lower level",
    "document": "exact checked local Markdown path without fragment: full document",
    "definitions": "whole owner body and its actual links",
    "unresolved": "delivered dependency gap => body-free dependency_incomplete refusal; unselected graph gaps are diagnostics only; no fetch or scope expansion",
    "syntax": "existing masked Markdown inline/full/collapsed/defined-shortcut/footnote and quoted HTML href/id/name; images are unsupported assets",
    "external_query_scheme": "unresolved; never fetched",
    "identity": "full native scope/version/generation/content/catalog identity, not path alone",
}
CONTRACT_SHA256 = hashlib.sha256(scoring.canonical(CONTRACT).encode()).hexdigest()
