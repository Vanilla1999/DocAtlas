# Task 29 — bound advanced and maintenance-only surfaces

Status: Done for bounded support-policy scope (`86d76d9`).

## Completion evidence

- `docmancer/support_surfaces.json` classifies the currently shipped surface inventory across `core`, `advanced-supported`, `maintenance-only`, and `internal` tiers, with ownership, documentation, test tier, network dependencies, current support policy, removal rules, and failure budgets for every non-core entry.
- `tests/test_support_surface_policy.py` introspects the complete Click command tree, public/advanced/admin Docs MCP configurations, MCP resources and templates, the Packs dynamic namespace, installed extras, connectors, stores, and the explicit shipped-service registration boundary. A newly shipped unclassified surface fails the policy contract.
- Core CI runs offline with `DOCMANCER_OFFLINE=1`; the test harness blocks unregistered outbound DNS and sockets, while advanced/maintenance contracts run in a separate release-blocking offline job and real live-provider work remains outside core CI.
- The pre-adoption purge removed stale inventory entries for local-path `add`, the `mcp serve` Packs alias, and the legacy dependency-prefetch identifier. The validator rejects deprecated tiers and compatibility metadata; policy covers the current release only.
- Runtime CLI help derives support-tier labels from the same inventory. Beginner documentation leads with the three-tool Docs MCP workflow, while advanced and maintenance surfaces link to `docs/support-surface-policy.md` and state their tier.
- The dependency policy records the current core set and leaves the Qdrant, FastEmbed, and document-reader install-profile decision to Task 24.

The implementation was merged to `main` in `86d76d9`. This post-Tasks-34–43 audit revalidated the inventory against `main` at `f8a30dc`; it does not promote maintenance-only surfaces or weaken shared security/storage release gates.

## Priority

P2 sustainability after core evidence is available.

## Problem

The repository still contains Packs, patch constraints, Qdrant management, USPTO ingestion, and broad maintenance CLI commands. Task 07 moved them out of the hero narrative, but support ownership, CI cost, removal rules, and network boundaries remain unclear.

## Goal

Keep the core Docs product reliable without pretending every historical surface has the same maturity or blocking core CI on unrelated external services.

## Required changes

1. Inventory every user-visible CLI group, MCP surface, service, connector, and installed extra.
2. Assign each item a support tier: core, advanced-supported, maintenance-only, or internal.
3. For every non-core item record owner/decision contact, documentation entrypoint, test tier, network dependencies, current support policy, and removal rule.
4. Separate core offline CI from optional live/advanced suites. Core tests must not fetch hosted registries because an optional local artifact is missing.
5. Remove stale compatibility inventory before adoption and enforce the current-only policy.
6. Define failure budgets: advanced network outages cannot make local Docs MCP unhealthy, while shared security/storage regressions still block release.
7. Make CLI help and docs label the current support tier.
8. Use the inventory to decide which dependencies remain in core versus task 24 extras.

## Non-goals

- Do not delete all advanced features in one PR.
- Do not rename the package.
- Do not lower security coverage for maintenance-only code.

## Acceptance criteria

- Every shipped surface has one support tier and test/release policy.
- Core CI is offline-hermetic and independent of optional hosted registries.
- Removed surfaces are absent from the inventory and current documentation.
- Beginner docs contain only core workflow; advanced docs state their tier.
- The inventory is machine-checkable enough to detect an unclassified new public surface.
- Policy checks and `git diff --check` pass.
