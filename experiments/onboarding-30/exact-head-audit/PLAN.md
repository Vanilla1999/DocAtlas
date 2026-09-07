# Exact-head retrieval audit — preregistered continuation

Date: 2026-09-06. Existing PR #178 and branch `fix/context-first-project-reads`.
Input head: `462fb13411cfd96ae2f1784c0a620b2601f86305`.

## Scope

1. Restore a separate local checkout from the preserved `3cae4f8` source bundle and verify runtime files against the input head. Direct local GitHub DNS is unavailable; do not confuse this reconstruction with the user's workstation or a deployed MCP server. No switch/merge/rebase of the divergent acceptance-closure branch.
2. Preserve current production/evaluator/corpus hashes, dependencies and raw public-call records outside indexed documentation. Existing 15 natural and 5 exposed cases use their unchanged input lookups; include the unchanged negative controls when possible.
3. Ask all 30 questions from `experiments/onboarding-30/questions.json` with question + project_path + scope=project, without supplied first-call lookups. Retain every response/error. Judge answer sufficiency separately from status, attribution, source identity and budgets.
4. Optional manual host clarifications: at most one extra call per original, at most two appended single-concept lookups within the existing five-lookup limit. Preserve question bytes, scope and existing lookups. Save proposals/declines before execution. Whole valid retry is used regardless of later scoring; errors/rejections keep baseline. No source splicing and no best-of-many selection. This is exposed coordinator exploration, not a blinded LLM benchmark.
5. Diagnose visible missing facts using existing retrieval/qualification/selection traces; unproven causes remain unclassified. Make only a small, general repair supported by RED → GREEN regression tests and broader checks. Commit verified implementation and tests together rather than leaving a test-only head.
6. Repeat affected questions and preserve gained AND lost facts. Commit the audit results and read back the published files. Do not merge based on scoped tests alone.

## Fixed boundaries

`docs_context` stays retrieval-only. `covered_query_ids` are attribution, not answer completeness. Scope, source identity, freshness, exact identifiers, hashes, spans, qualification thresholds and the 3-source/800-estimated-token budget stay authoritative. Frozen evaluator/corpus/thresholds and indexed witness documents are not edited to improve scores. No models, external model API, OpenCode, installed-agent experiment or persistent project sync.

## Lightweight design and test method

Use existing domain policies for pure evidence/window rules and application orchestration for allocation. No new service layer, NLP dictionary or universal semantic verifier. TDD sequence: list concrete failures; observe the relevant failure before implementation; minimal implementation; refactor with tests; check regression scope and runtime output.

Method references consulted:
- https://martinfowler.com/bliki/TestDrivenDevelopment.html
- https://martinfowler.com/bliki/DomainDrivenDesign.html
- https://martinfowler.com/bliki/BoundedContext.html

This file is a checkpoint plan, not a report of completed measurements. No new numerical result is claimed here.
