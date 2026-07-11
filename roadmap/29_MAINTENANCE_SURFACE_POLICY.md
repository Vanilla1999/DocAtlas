# Task 29 — bound advanced and maintenance-only surfaces

## Priority

P2 sustainability after core evidence is available.

## Problem

The repository still contains Packs, patch constraints, Qdrant management, USPTO ingestion, broad legacy CLI commands, and compatibility APIs. Task 07 moved them out of the hero narrative, but support ownership, CI cost, deprecation rules, and network boundaries remain unclear.

## Goal

Keep the core Docs product reliable without pretending every historical surface has the same maturity or blocking core CI on unrelated external services.

## Required changes

1. Inventory every user-visible CLI group, MCP surface, service, connector, and installed extra.
2. Assign each item a support tier: core, advanced-supported, maintenance-only, deprecated, or internal.
3. For every non-core item record owner/decision contact, documentation entrypoint, test tier, network dependencies, release compatibility promise, and removal/deprecation rule.
4. Separate core offline CI from optional live/advanced suites. Core tests must not fetch hosted registries because an optional local artifact is missing.
5. Review deprecations whose stated removal version has already passed; either remove through an explicit breaking plan or publish a new bounded deadline.
6. Define failure budgets: advanced network outages cannot make local Docs MCP unhealthy, while shared security/storage regressions still block release.
7. Make CLI help and docs label support tier without removing compatibility unexpectedly.
8. Use the inventory to decide which dependencies remain in core versus task 24 extras.

## Non-goals

- Do not delete all advanced features in one PR.
- Do not rename the package.
- Do not lower security coverage for maintenance-only code.

## Acceptance criteria

- Every shipped surface has one support tier and test/release policy.
- Core CI is offline-hermetic and independent of optional hosted registries.
- Expired deprecation promises have an explicit resolution.
- Beginner docs contain only core workflow; advanced docs state their tier.
- The inventory is machine-checkable enough to detect an unclassified new public surface.
- Policy checks and `git diff --check` pass.
