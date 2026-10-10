# PR211 — preserve truthful missing-module diagnostics under delivery veto

Runtime evidence: `bfe9709-agent-developer-v2.json` contains five rejected module selectors with correct no-source/read-only response, but no `operational_reason_code`. These are `traversal_module_path_rejected`, `absolute_module_path_rejected`, `prefix_collision_module_path_rejected`, `case_collision_module_path_rejected`, `long_missing_module_path_bounded`. Every failure is exactly `operational reason=None expected='module_not_found'`.

## Current contract, not expectation matching

`_ProjectDocsServicePart01._resolve_module_filter` resolves an explicit module_path against catalog module selectors. It does not canonicalize a traversal, absolute, prefix, case-changed or absent identifier into a different module. An unmatched selector returns `module_not_found` from the project service. The unified service preserves that factual failure in `lanes.project.reason_code` using `_project_module_recovery_metadata`.

At the MCP boundary, `_explicit_delivery_block` correctly enforces no delivery before any recovery processing. Its early return, however, bypassed the existing `_bounded_project_operational_diagnostics` adapter. The final response therefore retained only general `required_evidence_missing` and `operational_status=not_found`, losing the actual module-selection failure. The existing public reason allowlist already includes `module_not_found`; there is no new taxonomy or inferred path meaning.

## Narrow change

Only `docmancer/docs/interfaces/mcp/context_tools.py` changes. Before validating an already blocked `docs_context` DTO, copy **only** `operational_reason_code` from the existing allowlisted diagnostics helper, if present. Refresh the canonical output estimate after this addition.

The original delivery decision, overall reason, confirmation state, read-only flags, empty sources/snapshot/read targets and early return remain. No module candidates, available paths, raw messages, private details or next action are copied. No retrieval, index preparation, filesystem operation, grant or implicit retry is introduced.

All five original negative expectations remain unchanged. Their no-escape/no-source/no-authority assertions remain mandatory. The existing `module_recovery_reason_projection_guard` mutant removes `module_not_found` from the allowlist and must now be killed by those same public reason assertions, after the complete baseline is green.

## Verification

AST of the changed production file; all five exact test expectations; unique existing mutation anchor and parsing of mutated source; `git diff --check`: PASS. Source hash and scope are in `module-failure-diagnostic-static-audit.json`.

Local repository runtime was not executed. Ordinary PR CI must confirm the public DTO, cost estimate, unchanged denial guards and intended mutation kill. Remaining Agent Developer positive fact loss is handled by the separate retrieval work; this change does not weaken those oracles.

## Integration inventory repair

The independently reviewed acceptance module rename from the prior docs slice also requires its five-node diagnostic hash. This commit repairs that one hash without changing labels or test selection. Static review of all 508 module inventories, including imported test functions, found no other mismatch, collision or unlisted test module. Runtime collection remains pending CI.

Independent source review: APPROVE for CI; five original path-security expectations remain unchanged.
