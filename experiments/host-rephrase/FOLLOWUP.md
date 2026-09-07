# PR178 follow-up: verified runtime fix and exploratory MCP reads

Date: 2026-09-06. This follows the historical snapshot in `STATUS.md`.
The user authorized continuing available implementation/review work and ordinary
MCP questions without waiting for unavailable isolated model generations.

## Delivered

Runtime/test/provenance commit: `33234d3de537e2afac92d8bb2116aec00e606a92`.
Branch remains `fix/context-first-project-reads`; PR remains #178.
The divergent acceptance-closure branch was not merged, rebased, or checked out.
Automatic host retry was NOT integrated.

Two concrete defects were reproduced and fixed:

1. Exact-document indexed-section recovery tagged candidates only with the path
   lookup. The actual identifier could be present in the body but never receive
   its real lookup attribution. Stored sections now pass through the existing
   query plan and `qualify_evidence` rules, including project identity and
   lifecycle checks. This does not add retrieval calls or invent parent coverage.
2. The path-only topic guard extracted CamelCase/uppercase substrings from the
   filename. `docs/REFERENCE.md` could match the heading `Reference` and admit a
   body containing `meet_type_extra` for a `meet_type` question. The guard now
   uses whole existing technical anchors and the ordinary substantive-body
   qualifier. A filename, heading, link, or identifier prefix is not topic proof.

No synonym dictionary, lexical threshold change, semantic verifier, extra
architecture layer, or automatic model call was added.

## Changed files in the runtime commit

- `docmancer/docs/application/_project_docs_service_part03.py`
- `docmancer/docs/application/docs_context_projection.py`
- `tests/docs/test_exact_document_fallback_context.py`
- `tests/diagnostic_labels.exact_document_fallback.json`
- `eval/agent_developer_v1/results/paraphrase-proofability.json`
- `eval/agent_developer_v1/results/mixed-evidence-provenance.json`
- `eval/agent_developer_v1/results/evidence-is-data.json`
- `eval/agent_developer_v1/results/p1-agent-truth-closure.json`

The four generated P1 reports had stale source identities. They were re-derived
using unchanged producers. Only source/provenance hashes changed, not case
outcomes, scores, corpus, thresholds, or decisions. The P1 closure still says
`AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN`.

The temporary publication workflow was removed in `baa95e4`. It guarded the
exact branch/parent and whole-file hashes, tested the patch with dependencies,
then pushed only these eight files. It did not merge or modify branch protection.
Its published patch is byte-identical to the locally reviewed patch.

## TDD and validation

| Check | Observed result |
| --- | --- |
| New behavioral cases before implementation | 5 failed, 3 passed |
| New behavioral cases after implementation | 8 passed |
| Existing recovery contract before implementation | FAIL at exact indexed-document recovery |
| Existing recovery contract after implementation | PASS |
| Recovery mutation gate | 6/6 mutants killed |
| Full offline suite in clean GitHub Python 3.12 environment | **3882 passed, 10 skipped**, 46 warnings |
| P1.4 derivation / self-test | PASS; 14 cases / 5 of 5 self-tests |
| P1.5 derivation / self-test | PASS; 7 cases / 6 of 6 self-tests |
| P1.6 derivation / self-test | PASS; 6 cases / 6 of 6 self-tests |
| P1 closure / self-test | PASS; outcome still NOT PROVEN / 4 of 4 self-tests |
| Python module size and whitespace | PASS |

The full-suite result comes from Actions run `34040226219`, artifact
`9991490152`, not from the incomplete local environment. The local focused run
had 1725 passed and five missing-w3lib failures. A broader local selection had
3717 passed, 22 failed, one skipped, with missing parser/vector/dependency
packages. Those local runs are not presented as successful complete suites.
No model weights were installed and no external model API or installed-agent
model experiment was invoked. The clean runner installed package dependencies
and ran the existing offline tests and in-process contracts.

Review was coordinator self-review, not an independent blind review of the
entire earlier 196-file branch. It checked the exact new patch, true lookup
attribution, source-local bounds, whole-file hashes, source-only report deltas,
and rejection of heading/link/prefix-only evidence. Lexical checks do not prove
arbitrary semantic equivalence.

## Frozen gates: measured, not waived or relabelled

Frozen v1 hermetic contract: **PASS**.
Frozen v1 live legacy lane: **FAIL before and after the fix**.
The pre-fix result was freshly reconstructed at the same isolated project path,
with the same environment. Both metric dictionaries and error lists are exactly
equal. The two modified source files were restored and re-hashed afterward.
This is not the old saved historical run.

| Frozen v1 legacy metric | Before | After |
| --- | --- | --- |
| Useful positive results | 12/15 | 12/15 |
| Top-1 fact-bearing results | 11/15 | 11/15 |
| Top-3 relevant results | 13/15 | 13/15 |
| Original-query coverage | 0 | 0 |
| False supported / false docs_answer | 0 / 0 | 0 / 0 |
| Maximum sources / estimated tokens | 3 / 760 | 3 / 760 |

These are **legacy v1 numbers**, not a new v2 natural/exposed score. V2 was not
rerun as a three-generation host-rephrase experiment. The old handoff 13/15 and
previous reconstruction 11/15 natural must not be conflated with this 12/15.

The live gate misses its unchanged usefulness, fact-bearing, Top-3 relevance,
and original-query-coverage minima. The separate frozen question-surface gate
is 97/100: cases 026, 027 and 073 still expect legacy behavior/usage proof for
`prepare_docs` and `docs_status`, while current parsing reports unresolved
clauses. Neither parser rules nor expected signatures were altered to turn
these red checks green.

All 1623 pre-existing tracked files were compared against the original source
manifest. Only the two runtime files and four generated reports differ. Frozen
evaluator implementations, corpus files, thresholds, active document contents,
and catalog remain unchanged. New tests and this follow-up report are additions.

## Exploratory public MCP requests

Eight original questions were saved before execution. Six received exactly one
additional call, with one or two appended host lookups. All original questions
remained byte-identical. All 14 public calls used the existing unpatched
`call_docs_tool_payload("get_docs_context", ...)` dispatcher against a temporary,
vector-free index of this repository. This is in-process MCP handling, not a
claim that the user's deployed server or workstation was exercised.

The coordinator had exposed project knowledge. These are ordinary exploratory
requests, not isolated generators, independent holdout, source-precision scores,
or a substitute for the planned 3 x 25 experiment. All results, including
unhelpful retries, were retained; payloads were not spliced or selected by gold.

| Question / topic | Appended lookup(s) | Observation after the single retry |
| --- | --- | --- |
| Что это за проект и какую задачу он решает? | `DocAtlas project purpose` | Still lacks a clear purpose answer; contributor identity is not product purpose. |
| Где проходит граница между поиском документации и доказанным ответом? | `documentation retrieval versus answer proof` | README wording about narrow `docs_answer` conflicts or ambiguously scopes project reads relative to ADR 0003; not counted as improved correctness. |
| Как мне обновить локальную документацию после переименования файла? | `documentation file renames index reconciliation` | Sync workflow visible, but no explicit rename/orphan handling fact; contributor material adds noise. |
| Что возвращает get_docs_context, если документации не хватает? | `get_docs_context insufficient documentation`; `documentation recovery next action` | Adds visible insufficient-evidence/no-support and bounded nonautomatic recovery guidance. |
| Какой порядок обработки get_docs_context от MCP до отбора фрагментов? | `get_docs_context request processing flow`; `documentation fragment selection` | Returns a tool/lifecycle sequence, not the requested internal MCP/application/gateway/selection flow. |
| Можно ли по covered_query_ids считать ответ полным? | `covered_query_ids answer completeness` | Adds useful text that retrieval lookups do not prove support or authorize an edit. |

Two exact-document questions were not retried: `AgentIndexGateway` and
`NonexistentLookupEngine` in `docs/modules/project-context-retrieval.md` both
returned no sources. Subsequent document inspection confirmed that the named
`AgentIndexGateway` identifier is absent there too; exact-identifier abstention
is appropriate, even though the document describes a generic retrieval gateway.

Across the 14 calls: at most **3 sources**, **753 actual estimated tokens**,
**3011 canonical UTF-8 bytes**; no answer/edit authorization. Eight extra lookup
strings were used across six extra calls. Total public-call time was 25.7515 s;
median 0.6701 s. Index setup is excluded; projection/validation are included.
No generator latency or formal model-effect statistic is claimed.

The manual results do not justify enabling automatic host retry. Some lookups
recover useful details, others add noise or still miss the requested aspect.

## Reproduction and remaining work

With package dependencies installed, from the repository root:

```sh
PYTHONPATH=. DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 pytest tests/ -m 'not live and not live_network' -q
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_recovery_contract_gate.py
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_recovery_mutation_gate.py
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_paraphrase_proofability_gate.py
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_mixed_evidence_provenance_gate.py
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_evidence_is_data_gate.py
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_p1_agent_truth_closure_gate.py
PYTHONPATH=. DOCATLAS_OFFLINE=1 python eval/project_context_quality_protocol.py --live
PYTHONPATH=. DOCATLAS_OFFLINE=1 python scripts/run_question_surface_gate.py
```

The last two commands are expected to show the recorded unresolved failures;
they are not skipped acceptance checks. The companion archive contains the
before/after frozen reports, new-test RED/GREEN logs, exact published patch,
CI logs, all manual requests/responses, and the provider-free manual-call script.

The available runtime fix is delivered. Global acceptance and merge are not
claimed: the unchanged live and question-surface gates remain red. Resolve the
concrete retrieval gaps and the documented contract discrepancies separately;
do not invent original attribution, lower thresholds, or tune rewrites until
a studied benchmark becomes green. The unavailable isolated-generation
experiment can remain deferred under the user's latest instruction.
