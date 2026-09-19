# Renderer contract review — 2026-09-19

Continuation of the attached structural-integrity / reader-view TDD plan.
Review base: `f111304579299ca1d9e7811c4e46dac8a17ec005` (PR #194).

## Scope and decision

The structural fix and P0–P5 experiments were already present on the branch;
this review does not repeat them, change retrieval, or integrate reader views
into a host. `presentation_not_supported_for_product_rollout` still stands.

Three deterministic contract gaps in the eval-only renderer were reproduced:

1. An explicit, unreviewed `schema_version` was interpreted with the current
   unversioned allowlist. It now raises `UnsupportedReaderView`, and rendering
   falls back to the complete raw JSON for either view arm.
2. `path` was accepted as a source field but then silently dropped. Preserve
   it verbatim, including when `path_or_url` is also present.
3. Missing/non-string snippets could become empty text or stringified data
   in the text arm. Both view arms now fall back to raw JSON without coercion.
   Empty strings, whitespace, Unicode and instruction-like **string** data
   remain valid and roundtrip unchanged.

No new interpretation of answer flags, no source rewriting, no runtime
changes, no new dependencies and no adjustment using validation outcomes.

## Fresh local evidence

Source-distribution runtime: `6e510c21ca332f1967dae4b90856aa66b4e18569`.
SDist SHA-256: `e471b656aa30dc0dc0a1c5080f546217585f6a21e68697728d57feb8b64b1771`.
The reviewed renderer blob matches the PR head exactly:
`b1dfe3110ef7471dd1f97fd060481ba5ca01d194`.
The intervening commits only removed temporary workflows and added reports.
This is a source distribution, not a git checkout or a frozen uv environment.

- New boundary tests before the change: **32 failed, 3 passed** (assertions,
  not import/collection errors).
- After the change, new boundary tests + existing reader-view/run-integrity
  tests + structural-item tests: **64 passed**.
- Byte-level compatibility: 20 original H20 packets + 40 frozen validation
  packets, all three arms = **180 renders, 0 changed**.
- No reader inference was rerun. The comparison preserves the previous
  rendered contexts; it is not 180 new model responses or a new quality claim.
- Compilation of the modified renderer and new test module succeeds.

Commands:

```sh
python -m pytest -q tests/evidence_quality_v2/test_reader_view_contract_boundaries.py
python -m pytest -q \
  tests/evidence_quality_v2/test_reader_view_contract_boundaries.py \
  tests/evidence_quality_v2/test_reader_views.py \
  tests/evidence_quality_v2/test_reader_run_integrity.py \
  tests/docs/test_structural_item_integrity.py
python -m compileall -q eval/evidence_quality_v2/reader_views.py \
  tests/evidence_quality_v2/test_reader_view_contract_boundaries.py
python -m pytest -q
```

## Full-suite limitation

The fresh local full-suite attempt stopped during collection: `w3lib` is
absent. Affected modules:

- `tests/docs/test_curated_sources.py`
- `tests/test_auto_detection.py`
- `tests/test_filtering.py`
- `tests/test_kotlin_partial_crawl.py`
- `tests/test_preindex_coverage.py`
- `tests/test_web_fetcher.py`

Result: **3 skipped, 6 collection errors**, exit 4 (the diagnostic-inventory
hook also sees missing collected modules). No dependency stub, skipped-test
filter or new dependency was introduced to hide this environment limitation.

The previously completed paired CI artifact (run `35446290434`, artifact
`10585279610`) reports 36 failed / 4015 passed vs 36 failed / 4050 passed.
Its original logs were rechecked using complete node IDs, including spaces:
36 identical failing node IDs, 0 candidate-only failures. That evidence
predates this renderer review and is **not** a fresh full-suite pass for this
new commit. Current CI remains a separate verification boundary.
