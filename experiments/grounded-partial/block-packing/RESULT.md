# Whole-block packing instead of mandatory short windows

## Decision

Implemented and ran the requested two-lane English-only projector experiment in PR #189. Mandatory 160/320/520/640-character alternatives are bypassed in the treatment, both when preparing variants and expanding a selected quote. The complete DTO still has the unchanged800 admission-token / three-source cap. Production code, retrieval inputs, qualification, selector, gold and models are unchanged.

**The uv-05 missing definition is restored. Broad replacement is not ready for promotion:** the unchanged frozen assessment goes from29/35 to28/35 because pydantic-02 loses its short approved prose witness and receives a long example instead. That example still contains relevant code/comments; this is not evidence that a live answering model would necessarily fail. No live model was run and the assessment was not amended.

## Exact comparison

67 unchanged English questions:35 within-budget positives and32 controls. Two lanes,134 full DTOs, not134 independent tasks. Control is the previously archived combined bounded-relaxation policy. Every control payload, assessment and admission count reproduced exactly before comparison.

| Measurement | Existing windows | Whole structural blocks |
|---|---:|---:|
| Frozen sufficient /35 |29|28|
| New sufficient cases |—|0|
| Lost frozen sufficient |—|pydantic-02|
| Mean complete DTO admission tokens |377.1791|380.0746|
| Maximum complete DTO |795|797|
| Longest emitted quote, characters |573|1418|
| Quotes longer than640 characters |0|4|
| Source entries |73|70|
| Source/snapshot/span/budget audit errors |0|0|

14 payloads and quote sets changed;53 remained identical. Two of32 controls changed, not zero. No control became sufficient. One previously supported required claim lost its frozen witness. Thirteen cases lost some old literal text, often an irrelevant suffix or replaced secondary context, not necessarily a necessary fact. All changed outputs were inspected. Average admission size increased approximately0.77%; no whole-task token saving is claimed.

## Implementation and scope

structural_blocks.py patches only _qualified_fragments and _expand_selected_snippets within a context manager. The existing temporary _docs_source(raw[:520]) call supplies source identity only; its prefix never becomes an emitted treatment variant. Both final fragment seams use original structural spans, not _focused_snippet, _projection_limits or an enlarged character ceiling.

Pinned experiment-only markdown-it-py4.2.0 (CommonMark+table) obtains positions in verified source files. Alternatives include complete paragraphs, tables/fences, lists and full top-level list items, plus contiguous combinations within one section. No quote is rendered, paraphrased, joined across gaps or emitted from outside an already-retrieved candidate. Files are read for structure, but no extra source text is added to retrieval. Existing source/project/snapshot/identity and assignment checks still apply to each actual alternative.

The existing candidate ranking and query-ID novelty selector are unchanged. Alternatives preserve attribution/component/assignment priorities, then shorter-complete/source-order ties. Final expansion tries containing complete alternatives largest-first, retaining the selected quote and its attribution/assignment witnesses only when the complete DTO fits.

These are **syntactic blocks, not a proof of semantic completeness**. HTML blocks and unclosed fences are not decomposed. PyMdown tab/admonition/include syntax is not fully understood: e.g. Check it: or === "CLI" can remain without rendered child content. External includes are not fetched. This is not a complete documentation renderer. Explicit work bounds abort on too many blocks/alternatives rather than silently reporting missing evidence.

## uv-05: a real missing component returns

Question: Compare first-match, unsafe-first-match and unsafe-best-match index strategies.

Control: one320-character quote, source lines143–146, definitions of the two unsafe strategies only; full DTO362 tokens.

Treatment: one775-character quote, source lines136–146, option context and **all three definitions**; full DTO472 tokens. The old quote remains inside the new one. The whole list was in the original rank1 candidate. No new retrieval/model, extra source text or larger packet budget was required.

Frozen assessment remains needs_review because its witness also includes the following dependency-confusion warning, in another candidate. This experiment does not revise gold or claim a new sufficient score. It restores an obvious missing component, while unchanged same-query selection still does not guarantee adding the separate warning.

## pydantic-02: why the strict score falls

Question: Does a UUID string pass strict validation from JSON and from Python in the same way?

Control:199-character statement at lines54–55 explicitly states that a UUID string is accepted from JSON but not Python; full DTO340 tokens.

Treatment: a1387-character complete code fence at lines144–194 is selected; full DTO712 tokens. It contains validation calls, errors and comments showing the same distinction. The original short paragraph is **still offered intact and qualified**. A non-mutating post-hoc cost trace confirms that adding it after the code block requires884 admission tokens, exceeding800. It is rejected after the large example has occupied the packet.

This is a selection/allocation tradeoff exposed by larger alternatives, not evidence that paragraphs must be chopped. The approved short witness disappears and packet cost more than doubles, but relevant code remains. No unmeasured live-agent failure or total loss of the underlying fact is asserted. No case-specific ranking change was added after inspecting this result.

## Large blocks and the remaining byte floor

Current accounting is max(pinned_BPE(full_DTO), ceil(serialized_UTF8_bytes(full_DTO)/4)). Removing the local ceiling does not remove this full-packet estimate.

Three synthetic repeated-text boundary probes (not representative documentation or accuracy cases):

| Paragraph chars | Pinned BPE full DTO | Byte estimate | Outcome |
|---:|---:|---:|---|
|1653|372|615|Whole paragraph emitted|
|3083|500|973|Whole paragraph offered and qualified, rejected by admission budget|
|19858|2030|5167|Whole paragraph offered and qualified, rejected without truncation|

The3000-character failure is now at the conservative **whole-packet budget**, not alternative generation. Its pinned BPE count fits800 but its byte estimate does not. The byte floor is deliberately unchanged here. It would be incorrect to claim every BPE-fitting block now passes admission. Using a named-tokenizer-only budget instead of the byte floor requires a separate product decision.

If no complete block fits, the existing insufficient DTO is returned. Its generic missing-safe-evidence message remains; a new public omitted_due_to_budget/partial-answer contract has NOT been implemented. Internal diagnostics correctly record token_budget. No automatic continuation or larger packet budget was added.

## Manual review of all14 changed packets

| Case | Tokens before→after | Observation |
|---|---:|---|
|fastapi-04|676→686|Credentials/default rule retained; whole1418-character arguments list replaces smaller excerpts, exposing unrelated options too.|
|starlette-02|770→655|Lifespan rule retained. Broken introduction replaced by full introduction/example; unrelated shallow-copy quote disappears.|
|typer-01|694→686|Exit code/non-error explanation retained; dangling HTML opener removed, but Check it: remains.|
|typer-03|377→369|Aborted! distinction retained; dangling HTML opener removed.|
|typer-07, partial control|402→394|Public exit-code fact retained; private deployment fact still unavailable; HTML opener removed.|
|pydantic-02|340→712|Short approved explanation replaced by larger relevant example; frozen sufficient lost.|
|pydantic-04|714→687|AliasPath explanation retained; nearby reference link removed from a secondary excerpt.|
|httpx-01|792→787|Timeout default/exception retained; secondary pool/connect blocks lose general/incomplete surrounding prose.|
|httpx-04|657→582|Pool timeout/limits retained; secondary connect excerpt becomes shorter and intact.|
|httpx-09, ambiguous control|373→358|Pool-timeout passage remains; incomplete suffix removed; deployment-specific recommendation still unavailable.|
|ruff-01|793→797|Direct preview rule retained; secondary config material changes; tab syntax not fully resolved.|
|ruff-04|790→796|Deprecated-rule behavior retained; secondary preview configuration changes.|
|uv-04|782→735|First-index behavior retained; clipped first-match becomes whole strategies block, but the requested reason is still absent.|
|uv-05|362→472|All three definitions now present; separate warning still missing.|

Literal losses are neither silently equated with factual losses nor assumed harmless on every future question. Frozen claim scoring and this utility review remain separate.

## Evidence and reproduction

Protocol published before results:4660aa1538721a1f23dd3b3b36bd356ffcf8b84d. Tested code:c5289a860f6e1275597ab6410b5dc17a2ebb7717. CI run34816081241 / job103886929795 completed successfully: **108 tests passed**, including25 new block/budget cases and83 previous qualification/research checks. The134-DTO English replay ran with real pinned tiktoken under kernel outbound-network denial after setup. Zero integrity/budget errors. No fresh full-project suite or public MCP/answer-model test is claimed.

Artifact10336620474, SHA25639c3629633e5da55deab199b0683f12348f4a607c5f9aee43ba1931a5d8099e5, downloaded and compared against the local run. All134 payloads, assessments, BPE/byte/admission counts and input fingerprints match. Both implementation files match the local code byte-for-byte. Local development used the explicit pinned-vocabulary Python BPE fallback from the prior uv-05 proof; final CI uses the native tokenizer. No latency comparison is claimed. Post-hoc884-token/long-block probes are observations, not score-changing policies.

The artifact contains code, tests, English input snapshots, complete before/after DTOs, source snapshots, qualification/block diagnostics and logs. It expires after14 days. Input archive10325979852 has SHA256f3e78c127d0c0fae4686da0613efd34c5f0c28ae3bb04bf8e4f25db834319c96. Save it for strict reproduction. Run with Python3.12, existing .[dev] dependencies and markdown-it-py4.2.0; set PYTHONPATH to the checkout and block-packing/, bounded-relaxation/, section-scope/; execute run_blocks.py --archive <input.zip> --output <new directory> under hypothesis5/no_network.py. The committed workflow records full commands.

## Conclusion

The artificial short-window restriction was unnecessary for the uv list. Removing it works locally, but does not make the existing selector choose the best affordable combination. Do not promote the broad replacement as a proven general improvement, and do not interpret a frozen witness loss as proof that all whole-block approaches are worse.

The next small concern is choosing a short complete explanation versus a long example under the same budget, not another character-threshold increase or reranker. Distinguish the named tokenizer budget from the remaining byte estimate as a separate issue. Neither was silently changed. Production and main remain unchanged; holdout20 stays closed.
