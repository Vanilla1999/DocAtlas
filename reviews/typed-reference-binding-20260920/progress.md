# SDD ledger — plan: TDD_PLAN_RU(3)(1).md

## Durable checkpoint: standalone P1/P2 contract

Remote product BASE: bf9c5951eb75347d5075ee6e040328fe50d6e804.
Branch: fix/typed-reference-evidence-20260920. No merge, release, force push or new workflow.

This commit adds the pure reference API and its tests; it does NOT enable the rejected OLD runtime.
The native source-attestation, pipeline integration and quality gates remain open.

- P0: recovered source from release-dist artifacts for a632 and OLD 80860e5. BASE runtime tree and tests tree match GitHub (822bf204 / 6969b726). Local release-snapshot commits are not upstream commit IDs.
- P0: identical native locator fixture returns all three Lumina capabilities on BASE and no sources on OLD. Frozen Click replay is still pending.
- P0 environment: uv sync --frozen --extra dev --offline failed (locked pydantic unavailable). Full offline core collection: six errors from missing dependencies. No stubs or uv.lock changes.
- P1/P2 RED: 56 failed, 3 passed; conservative API existed, failures were assertions/empty occurrences rather than ImportError.
- P1/P2 GREEN: 59 passed. Tests cover original Unicode offsets, repeated spelling in two roles, contextual quoting, longest spans, dynamic aliases, case collisions, complete catalog, project/version/snapshot isolation, traversal and missing sources.
- Checkpoint on BASE plus only these new files: 89 passed, including existing query lineage and catalog tests. Command: python -m pytest tests/docs/test_query_reference_roles.py tests/docs/test_source_locator_resolution.py tests/docs/test_review_query_lineage.py tests/docs/test_project_docs_catalog.py -q.
- These are local runs with actual installed dependencies, not a successful frozen-environment gate.

## Interface rulings

Reference offsets belong to the original question; no normalized-word role map.
Path resolution requires a complete prefiltered catalog; top-k does not prove uniqueness.
Project documents may be unversioned, but a real project/snapshot identity is mandatory.
Resolver document_suffixes is injectable; P3 must pass the existing catalog's SUPPORTED_EXTENSIONS. The default matches the pinned source format contract and has an equivalence test.
Unresolved weak mentions do not become new hard subjects. Explicit missing/ambiguous locators retain source obligations.
The approved spec/plan is the design authority. Checkpoints must be saved before large integration work.

## Next exact steps

P3: prepare source/owner evidence from the current allowed index snapshot; add native positive and metadata-forgery negatives before activation. Do not assume the previous chat's serialization diagnosis is established.
P4: retain occurrence/scope constraints through lookup, variant and final crop; no filesystem/network I/O in qualification/projection.
P5/P6: retain composite facts and run behavioral/mutation controls.
P7: paired BASE/NEW Target30, both Generic30 modes, external80 and exposed transfer24; compare actual failures/reasons and latency.
P8: only after P7 acceptance, freeze new source-separated validation. No independent validation has run.
