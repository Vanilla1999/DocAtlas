# TDD and newcomer audit — not ready to merge

Date: 2026-09-06. Existing branch `fix/context-first-project-reads`, PR #178.

## Publication boundary

Published through the GitHub plugin:

- `79cb0b7a98e93b89214d9f5d7e160e2e6f053f07`: regression tests first (RED).
- `38ee3d80eaf1277c1fd52d3178cb7eb7e017a8e6`: first projection/window implementation (GREEN on focused tests).
- `da1edec8d629bdc4679dc68868b5f3cffc51db20`: the fixed 30-question input list.

**BLOCKING: the final review fixes are NOT published.** The tool safety check twice blocked `GitHub.create_blob` for the reviewed window module. The second call used identical contents; no alternative encoding, publication workflow, or other write route was used to bypass the block. The tested review patch is preserved in the companion chat artifact `docatlas-review-fixes-pending.patch`, not in this branch.

The published first iteration still loses some visible witnesses. Its exact projection replay over the same recorded candidate pools yields **12/15 natural and 2/5 exposed**. This is a controlled projection replay, not a new deployed-server/live-gate run. Fresh public-handler calls using the locally reviewed fixes yield **13/15 natural, 3/5 exposed, false-full=0**. Do not attribute those local results to the published runtime. Do not merge this PR.

## TDD and lightweight DDD

Method references read before implementation:

- https://martinfowler.com/bliki/TestDrivenDevelopment.html
- https://martinfowler.com/bliki/DomainDrivenDesign.html
- https://martinfowler.com/bliki/BoundedContext.html

The existing retrieval vocabulary and boundaries were retained. Pure contiguous-source-window rules were extracted to `docmancer/docs/domain/context_windows.py`. Application code still assembles the payload; MCP remains an adapter. No new service, aggregate hierarchy, NLP subsystem, synonym inventory, or semantic verifier was introduced. The existing query stop words and normative predicates were reused; qualification thresholds and public schemas were not weakened.

Published fixes: the stale second call to `_has_visible_non_path_exact_term`; clipping of words/table endings; stronger explicit match ratios before generated-query bonuses; preservation of already visible recognized normative text during expansion.

Local review reproduced further failures: a requested table role could disappear while its description survived; a rolling prose window could lose the subject of a short sentence; an oversized normative sentence could become an unfinished restriction. These have local RED/GREEN tests, but their implementation publication is blocked.

An additional lexical-score tiebreaker was tried and REJECTED: it gained one request-flow fact but regressed catalog and freshness answers. Neither that implementation nor its proposed contract test is in the final code. Frozen expectations were not adjusted to accept it.

These structural guards are not a certificate for arbitrary meaning. The bounded leading-cell exception retains no recognized normative or requested terms in the omitted prefix; continuous source ranges and ordinary qualification remain mandatory.

## Validation

| Check | Result / exact scope |
|---|---|
| Published new regression cases | 11 |
| Final local review cases | 16 passed |
| Final local focused projection/generic/compound tests | 103 passed |
| Available documentation modules, final local review | 1631 passed |
| Recovery contract | PASS |
| Recovery mutation gate | 6/6 mutants killed |
| Compile / whitespace / module size | PASS |
| Entire local repository suite | NOT claimed as rerun successfully |
| CI 34046707813 at 38ee3d8 | Core 3.11/3.12/3.13 and advanced unit step PASS; recovery/hermetic PASS; live gate FAIL; overall FAIL |

Two local modules were excluded from the explicit 90-module command because `w3lib` was unavailable: `tests/docs/test_curated_sources.py` and `tests/docs/test_dartdoc_discovery.py`. Package installation failed on DNS. No test expectations or diagnostic inventory were changed to hide those exclusions. One focused command was interrupted by a 40-second coordinator timeout and then completely rerun (103 passed); the interrupted attempt is not PASS.

All 1625 original tracked files were compared with the local baseline: only application projection changed. New domain/test/data files are separate. Frozen evaluator, corpus, thresholds, catalog, and active witness documents are unchanged. Earlier 3882/593 counts are not reused as new local results.

## Thirty newcomer questions

Exact wording is in `questions.json`. These questions were saved before calls. First calls used only `question`, `project_path`, and `scope=project`, without supplied lookups. This is a raw diagnostic mode, not a benchmark of an independently configured agent following the host-decomposition policy.

After reading the first public payloads, 24 one-retry decisions and 6 declines were fixed before further calls. Each retry appended at most two single-concept lookups, kept the question bytes and scope unchanged, and selected the whole valid retry regardless of gold. No sources were spliced. On the final local reviewed implementation, exactly the same questions and the same 24 lookup texts were replayed; the earlier published-version captures remain separate.

Both versions completed 30 first calls and 24 additional public-handler calls. The final first calls returned 16 `ok` and 14 `insufficient_evidence`. Manual first-payload review found 6 sufficient answers. After the fixed clarifications: **13 sufficient, 11 partial, 5 off-topic, 1 unestablished capability**. These are post-hoc coordinator judgments, NOT frozen evaluator scores or weak-model accuracy. Question 29 is an unsupported-capability control: lack of a witness proves neither presence nor absence of encryption.

All recorded responses passed the ordinary source/hash/span/budget validator. Maximum: 3 sources, 788 actual estimated tokens before clarifications, 799 after. Safe output shape is not semantic usefulness.

| ID | After fixed clarification / baseline retention | Main observation |
|---|---|---|
| 01 | sufficient | Product purpose and coding-agent problem retrieved |
| 02 | partial | External acquisition confirmation, incomplete local/network boundary |
| 03 | partial | Setup/ingest instead of package installation and CLI identity check |
| 04 | sufficient | README, CONTRIBUTING, INDEX, PROJECT_MAP |
| 05 | sufficient | Read-only first-call preflight and returned preparation |
| 06 | sufficient | Three public tools and principal roles |
| 07 | sufficient | get_docs_context is the first documentation call |
| 08 | off-topic | Stale/missing-doc states instead of found-but-not-indexed |
| 09 | partial | Job status only, no complete state/call conditions |
| 10 | partial | One preparation example, no general every-question rule |
| 11 | sufficient | Host formulates up to five single-concept lookups |
| 12 | sufficient | Attribution does not add proof or edit authorization |
| 13 | sufficient | docs_context alone does not establish edit readiness |
| 14 | off-topic | Missing-document authoring instead of partial-answer recovery |
| 15 | partial | Application/domain responsibilities, incomplete MCP/storage boundary |
| 16 | off-topic | Tool usage order, not the internal request pipeline |
| 17 | off-topic | Existing formats/options, not an extension implementation path |
| 18 | partial | Product/package/import names, no historical rationale |
| 19 | sufficient | Repository files authoritative, index derived |
| 20 | partial | Catalog versus runtime config, no required schema fields |
| 21 | sufficient | Bounded roots and local index links |
| 22 | sufficient | Invalid catalog blocks operations without pruning the index |
| 23 | partial | Sync after edits; rename/orphan details missing |
| 24 | sufficient | Preview before explicit apply; preserve source/config |
| 25 | sufficient | Per-project SQLite/artifact isolation |
| 26 | partial | Global configuration retention, incomplete preserved-file inventory |
| 27 | off-topic | Chunk sizes instead of avoiding model downloads |
| 28 | partial | Manifest validation/advisory report, no required test commands |
| 29 | unestablished | No encryption/key-management witness; do not invent a guarantee |
| 30 | partial | Source metadata and unsupported flags, missing agent-check details |

Calls used the existing in-process public `get_docs_context` handler and a temporary vector-free project index, not the user's deployed MCP or workstation. No OpenCode, model API, model-weight installation, or installed-agent experiment was used. Existing CI independently ran its normal scripted harness. The coordinator already knew the project; this is not a blind holdout or three independent model generations.

## Remaining work, not hidden by unit tests

For request-flow the relevant project-context document is in the candidate pool and its application fragment qualifies, but selection still chooses adjacent tool-usage information. Other missing stages have retrieval/qualification gaps. A coarse stage label does not establish the cause for every missing witness.

The new questions expose broader topic mismatch than the prepared 15-case corpus. Installation can retrieve fetcher-extension instructions; embedding opt-out can retrieve chunk sizes. Boundary repair alone cannot solve this. Automatic host retry was not integrated and its general benefit remains unproven.

First complete publication and verification of the pending review fixes. Then investigate missing source spans and first-call host planning with gains AND losses preserved. Do not tune a synonym dictionary, lower thresholds, splice payloads, or change frozen witnesses to manufacture acceptance.

The companion archive preserves raw first/retry responses for both revisions, all fixed proposals/declines, private diagnostic pools, final and rejected-control measurements, RED/GREEN logs, source hashes, full manual question answers, and the unapplied review patch. Earlier `experiments/host-rephrase/STATUS.md` and `FOLLOWUP.md` remain historical records.

No merge/rebase, force push, or switch to the divergent acceptance-closure branch occurred. The user's local workspace and old `/tmp/opencode` remain unverified.
