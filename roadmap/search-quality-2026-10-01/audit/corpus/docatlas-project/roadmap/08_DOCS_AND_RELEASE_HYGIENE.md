# Task 08 — align product documentation and release maturity

## Audit status

Done for documentation and release-hygiene scope. The original alignment landed in `66c1e2a` and review follow-up `311eba6`; the closing audit adds executable documentation contracts and reconciles the roadmap with the completed release gates.

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

## Completion evidence

- The active product narrative is local-first documentation context, with patch constraints labelled advanced/advisory.
- The default Docs MCP inventory is exactly `get_docs_context`, `prepare_docs`, and `docs_status`.
- `tests/docs/test_documented_cli_contract.py` checks active Markdown commands and options against the Click command tree without executing them.
- `tests/docs/test_user_facing_docs_branding.py` protects package naming, Git trackability, the canonical workflow boundary, and the 1,000-line release-documentation budget. The checked set is 423 lines at closure.
- `pyproject.toml` remains `Development Status :: 4 - Beta`.
- Task 15's release workflow builds wheel/sdist once, tests Python 3.11-3.13, runs the installed primary stdio smoke, and keeps publication behind the explicit release environment.

Residual ownership remains separate: Task 14 owns live external-ingest closure, Task 18 owns comparable Context7 capture, Task 21 owns generated/installed agent wording, and Stable promotion requires an explicitly approved post-publish verification of the exact public release.
