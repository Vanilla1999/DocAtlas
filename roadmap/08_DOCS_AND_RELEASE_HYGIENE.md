# Task 08 — align product documentation and release maturity

## Problem

Current documents describe different products: README leads with documentation context, the product brief emphasizes Patch Contract Runtime, and old roadmap prompts describe already completed work. Recent MCP, exact-dependency, docs-impact, and agent-contract changes are not fully represented in `CHANGELOG.md`.

## Goal

Create one consistent product narrative and a release checklist that prevents documentation drift.

## Required changes

1. Update `docs/DOCMANCER_PRODUCT_BRIEF.md` to the current local-first documentation context direction.
2. Keep patch constraints in an explicit experimental/advanced section.
3. Update `CHANGELOG.md` Unreleased with the three-tool surface, npm/Python project dependency detection, docs-impact CI, and agent contract.
4. Add a short release checklist covering version bump, changelog, README commands, installer smoke, MCP public-tool snapshot, and PyPI metadata.
5. Re-evaluate the `Production/Stable` classifier. Keep it only if the documented primary flow has a release-level smoke test.

## Non-goals

- Do not rewrite all historical release notes.
- Do not rename the Python package in this task.
- Do not remove compatibility commands.

## Acceptance criteria

- README, product brief, AGENTS, MCP workflow docs, and changelog agree on the three public tools and product purpose.
- No active document calls DocAtlas primarily a Patch Contract Runtime.
- Every user-facing command shown in docs exists in `--help`.
- CI includes a check for the default MCP public-tool inventory.
