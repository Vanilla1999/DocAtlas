# Measured checkpoint before further implementation

Input runtime: `462fb13411cfd96ae2f1784c0a620b2601f86305`.
Plan checkpoint: `146d7a80d25ebbcc1237075059e55a258b4cbcaa`.
New calls in this continuation; not reuse of historical scores.

## Reconstruction and integrity

A separate local copy was reconstructed from the preserved 3cae4f8 bundle. All four changed runtime files matched GitHub git-blob hashes at the input head:

- `_project_docs_service_part03.py`: `a11335843cbd9a62bcf036470b2244ee840e3714`
- `docs_context_projection.py`: `e167c5f95fb342c809368596e9a5a0fadf687936`
- `context_windows.py`: `52a68e4aba9c9ce5188109ccea45536ab330807c`
- `query_terms.py`: `a5ff8bed4915d164ff34a5cb7bfd216387c0ee62`

Frozen evaluator, corpus, thresholds, indexed documents and catalog are unchanged from the source snapshot. Four previously published derived P1 reports were restored separately; they are not runtime changes. This is not the user's workstation or deployed server. A temporary vector-free index was used; no model API, OpenCode or persistent project indexing.

## First-call v2 evaluation

Unchanged v2 evaluator, unchanged original questions/lookups/scopes (including scope=all where the frozen input specifies it):

| Lane | Useful |
| --- | --- |
| Natural | 11/15 |
| Exposed paraphrases | 3/5 |

False-full: 0. Safety, source identity, budget, estimated-token presence and authorization-denied checks: 25/25 each. Public projection/citation validation also passed for the collected calls.

Missing accepted obligations:
- architecture: infrastructure_boundary;
- request-flow: flow_mcp, flow_application, flow_gateway, flow_selection;
- stale-health: sync;
- storage: isolation;
- review-ready: test;
- search-trust: not_proof.

The historical 13/15 is not the measurement of this input/runtime reconstruction. The returned storage excerpt begins with `isolated SQLite index` after omitting its subject; the stale-health excerpt begins mid-enumeration and omits the canonical sync instruction. Those are visible losses, not yet a claim of the precise failing internal stage. The search-trust evaluator may reject semantically equivalent evidence from another path; keep formal scoring and manual judgments distinct.

## Thirty newcomer questions

All 30 fixed inventory questions were actually called with no initial lookups. First results: 16 `ok`, 14 `insufficient_evidence`. These statuses are NOT sufficiency scores.

After reading public first payloads, 24 manual rewrite proposals and six declines were sealed before executing any additional calls. All 24 additional calls completed; two remained insufficient (`newcomer-20`, `newcomer-27`). Original question bytes and project scope were preserved; at most two lookups were appended. No payload splicing. This is a new exposed coordinator exploration, not the lost previous set of rewrites or an independent model experiment.

Total saved calls: **79** = 25 frozen v2 inputs/controls + 30 newcomer first calls + 24 newcomer retries. All public responses, requests, timings and separate private snapshots/diagnostics have been retained locally for the final archive. Semantic review of the thirty final contexts and implementation follow in this same continuation; no all-green claim is made here.
