# Task 08 — align product documentation and release maturity

## Audit status

Open and next. The 2026-07-11 audit found every major drift named below still present, plus installer/PyPI and model-instruction drift.

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
6. Align factual wiki command/troubleshooting pages and `CONTRIBUTING.md` with the same workflow. Leave generated/installed agent-contract wording to task 21.
7. State clearly whether the one-line installer installs the code described by the current README. Do not present an unreleased `main` workflow as available from PyPI.
8. Normalize the `docs/` ignore/allowlist policy so a newly added active documentation file cannot be silently ignored while neighboring tracked files are accepted.
9. Choose one canonical detailed workflow document and set a duplication/size budget for active user/model docs. Link to it instead of maintaining several thousand-line overlapping explanations.

## Non-goals

- Do not rewrite all historical release notes.
- Do not rename the Python package in this task.
- Do not remove compatibility commands.

## Acceptance criteria

- README, product brief, AGENTS, MCP workflow docs, and changelog agree on the three public tools and product purpose.
- No active document calls DocAtlas primarily a Patch Contract Runtime.
- Every user-facing command shown in docs exists in `--help`.
- CI includes a check for the default MCP public-tool inventory.
- Factual user-facing install instructions use the `doc-atlas` package name and contain no developer-local paths.
- Commands shown as primary, including the MCP server command, are discoverable from the documented `--help` path or the docs explicitly show the intermediate help command.
- A repository test proves every intended active `docs/` path is tracked/trackable under `.gitignore`.
- Until task 15 proves the built release artifact, the maturity classifier is no higher than Beta.
