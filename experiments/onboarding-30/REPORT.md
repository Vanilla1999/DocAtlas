# TDD and newcomer audit — runtime fixes published, acceptance still open

Date: 2026-09-06. Existing branch `fix/context-first-project-reads`, PR #178.

## Publication boundary

Published through the GitHub plugin on the existing branch:

- `79cb0b7a98e93b89214d9f5d7e160e2e6f053f07`: projection regression tests first (RED).
- `38ee3d80eaf1277c1fd52d3178cb7eb7e017a8e6`: first projection/window implementation.
- `da1edec8d629bdc4679dc68868b5f3cffc51db20`: fixed 30-question newcomer input list.
- `afb562715de5b1d68759dd2b58e4e1b73929f41b`: review regressions for exact-witness loss, table subjects, and anchor extraction.
- `d03c4c66154cd63e1244d33ca795587e6b8d2e85`: keep filename anchors whole without inventing standalone identifiers.
- `866f65e48f4aafb3039da4f765396ddf38f85e0d`: keep complete table rows and allow a short complete source witness while the public 800-token budget remains authoritative.
- `1ca0b0adfbd21c00069e2dca842dac1c358363a1`: final reviewed projection fix: retain exact witnesses during bounded expansion, use bounded source-local projection limits, and refine exact-anchor candidate ordering without globally promoting assigned evidence.

The earlier publication blocker is **closed**. The final review fixes are now in the branch. A transient exact-branch workflow was used only to apply and verify the large projection patch after the direct blob path was blocked; the successful runtime commit removed that workflow from the repository. The first transient run stopped before modifying code because its textual guard did not match; the second run `34052342546` completed successfully.

The final runtime commit uses `[skip ci]`, so it does not imply that the repository-wide normal CI or frozen live gates are newly green. The successful publication workflow verified the selected regression and existing project-context contracts in a clean Python 3.12 environment before committing the runtime file.

## TDD and lightweight DDD

Method references read before implementation:

- https://martinfowler.com/bliki/TestDrivenDevelopment.html
- https://martinfowler.com/bliki/DomainDrivenDesign.html
- https://martinfowler.com/bliki/BoundedContext.html

The existing retrieval vocabulary and boundaries were retained. Pure contiguous-source-window rules live in `docmancer/docs/domain/context_windows.py`. Application code still assembles and selects the model-visible payload; MCP remains an adapter. No new service, aggregate hierarchy, NLP subsystem, synonym inventory, or universal semantic verifier was introduced. Qualification thresholds and public schemas were not weakened.

Published fixes now cover:

- the stale call to `_has_visible_non_path_exact_term`;
- clipping of words and table rows;
- preservation of row subjects and restrictions instead of exposing row suffixes;
- preservation of an already selected exact or normative witness during snippet expansion;
- short complete source/table witnesses when they remain under the global product budget;
- stronger explicit match information without letting generated aliases or global assignment priority crowd out action evidence;
- exact-anchor identity lanes preferring the upstream assigned witness only inside that lane;
- filename/qualified anchors remaining one source identity instead of generating duplicate embedded identifiers.

An additional general lexical-score tiebreaker and a global assigned-evidence priority were both tried and rejected because they improved one case while regressing catalog/freshness or procedural/action witnesses. Neither rejected behavior is in the final code. Frozen expectations were not adjusted to accept those attempts.

These structural guards are not a certificate for arbitrary semantic equivalence. Output remains a contiguous source span, ordinary evidence qualification remains mandatory, and retrieval coverage still does not authorize an answer or edit.

## Validation

| Check | Result / exact scope |
|---|---|
| Published projection/context-preservation regression suites | PASS on final local review and clean publication run |
| `tests/docs/test_docs_context_compound_projection.py` | 26 passed on final local review; clean publication step PASS |
| `tests/docs/test_context7_style_project_chat.py` | 47 passed on final local review; clean publication step PASS |
| `tests/test_docs_service_part03.py` | 24 passed on final local review; clean publication step PASS |
| Exact-document fallback / new regression cases | PASS |
| Targeted generic workflow facts and stale-health | PASS on clean publication run |
| Recovery contract | PASS in earlier verified follow-up |
| Recovery mutation gate | 6/6 mutants killed in earlier verified follow-up |
| Compile / whitespace | PASS locally and in publication workflow |
| Final runtime publication workflow | **PASS — run 34052342546** |
| Entire repository suite after `1ca0b0a` | NOT claimed as rerun successfully |
| Frozen live/global acceptance after `1ca0b0a` | NOT claimed green |

The clean publication job installed the normal development dependencies, applied the reviewed patch, ran the selected regression plus existing project-context suites, and only then created `1ca0b0a`. The transient workflow deleted itself in that commit. This is stronger evidence for the published runtime bytes than the earlier local-only review, but it is deliberately not described as a full repository acceptance run.

Frozen evaluator, corpus, thresholds, catalog, and active witness documents were not changed to manufacture acceptance. Earlier 3882/593 counts are historical and are not reused as a new final-head full-suite claim.

## Thirty newcomer questions

Exact wording is in `questions.json`. These questions were saved before calls. First calls used only `question`, `project_path`, and `scope=project`, without supplied lookups. This is a raw diagnostic mode, not a benchmark of an independently configured agent following the host-decomposition policy.

After reading the first public payloads, 24 one-retry decisions and 6 declines were fixed before further calls. Each retry appended at most two single-concept lookups, kept the question bytes and scope unchanged, and selected the whole valid retry regardless of gold. No sources were spliced.

The recorded newcomer audit completed 30 first calls and 24 additional public-handler calls on the reviewed local implementation that preceded the final publication cleanup. The first calls returned 16 `ok` and 14 `insufficient_evidence`. Manual first-payload review found 6 sufficient answers. After the fixed clarifications: **13 sufficient, 11 partial, 5 off-topic, 1 unestablished capability**. These are post-hoc coordinator judgments, NOT frozen evaluator scores or weak-model accuracy. Question 29 is an unsupported-capability control: lack of a witness proves neither presence nor absence of encryption.

All recorded responses passed the ordinary source/hash/span/budget validator. Maximum: 3 sources, 788 actual estimated tokens before clarifications, 799 after. Safe output shape is not semantic usefulness.

Because `866f65e`/`1ca0b0a` were published after that capture, the 30-question numbers above are **historical diagnostic results, not an exact current-HEAD rerun**. The appropriate next audit is to replay those same saved questions on the exact published head, retaining all gains and losses rather than rewriting the questions after seeing answers.

| ID | After fixed clarification / baseline retention | Main observation in the saved audit |
|---|---|---|
| 01 | sufficient | Product purpose and coding-agent problem retrieved |
| 02 | partial | External acquisition confirmation, incomplete local/network boundary |
| 03 | partial | Setup/ingest instead of package installation and CLI identity check |
| 04 | sufficient | README, CONTRIBUTING, INDEX, PROJECT_MAP |
| 05 | sufficient | Read-only first-call preflight and returned preparation |
| 06 | sufficient | Three public tools and principal roles |
| 07 | sufficient | `get_docs_context` is the first documentation call |
| 08 | off-topic | Stale/missing-doc states instead of found-but-not-indexed |
| 09 | partial | Job status only, no complete state/call conditions |
| 10 | partial | One preparation example, no general every-question rule |
| 11 | sufficient | Host formulates up to five single-concept lookups |
| 12 | sufficient | Attribution does not add proof or edit authorization |
| 13 | sufficient | `docs_context` alone does not establish edit readiness |
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

Calls used the existing in-process public `get_docs_context` handler and a temporary vector-free project index, not the user's deployed MCP or workstation. No OpenCode, model API, model-weight installation, or installed-agent experiment was used. The coordinator already knew the project; this is not a blind holdout or three independent model generations.

## Remaining work, not hidden by unit tests

The publication blocker is closed. Remaining work is product-quality and acceptance work, not missing runtime bytes.

For request-flow the relevant project-context document was observed in the candidate pool and an application fragment qualified, while selection/retrieval of the full internal sequence remained weak in the saved audit. Other onboarding failures include first-call topic mismatch such as installation retrieving setup/ingest material and embedding opt-out retrieving chunk-size material. These should be diagnosed by retrieval → qualification → selection/projection stage; do not solve them by growing a synonym dictionary or lowering qualification thresholds.

Automatic host retry is still not integrated as an unconditional server behavior. Its general benefit remains unproven: manual retries helped some questions and harmed or failed others. If revisited, keep the original question unchanged, append bounded single-concept lookups, use at most one retry, and preserve the whole baseline on refusal/error/invalid result.

Next: rerun the saved 15/5 quality questions and the saved 30 newcomer questions on the exact published head `1ca0b0a` (or its documentation-only descendant), compare visible facts and lost facts, then address concrete stage failures. A successful full offline suite and frozen live/surface gates are still required before merge acceptance.

Earlier `experiments/host-rephrase/STATUS.md` and `FOLLOWUP.md` remain historical records. No merge/rebase, force push, or switch to the divergent acceptance-closure branch occurred. The user's local workspace and old `/tmp/opencode` remain unverified.
