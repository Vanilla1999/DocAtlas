# NL dictionary removal — inventory / execution manifest

Baseline `6e94d6ab`, primary PR211. Новый проход не использует legacy compatibility
tests как gate. Historical reports/test results immutable; fresh compatibility,
quality/release UNKNOWN. No network/reinstall/index rebuild. D1 exact10docs/codeempty.

## Конечный стартовый scope и ownership

| Symbols / decisions | Definitions | Consumers | Owner / removal |
|---|---|---|---|
| `_RISK_PATTERNS`, `detect_instruction_like_patterns` | domain/content_trust.py | annotate_context_pack | A: remove NL detection; retain inert annotation |
| `_DANGEROUS_CONTENT_PATTERNS`, `_content_instruction_risk_flags`, `_instruction_risk_flags` | application/_action_packet_shared.py, _action_packet_part01.py | witnesses, fitting, facts/snippets, exports in part01–04/action_packet | A: remove definitions and risk-dependent omission; retain source/budget/auth checks |
| `_may_guide_workflow` | _action_packet_part02.py | part03 | A: inert deny remains independent of detector; remove unreachable prose-promotion branches if needed |
| risk_flags/candidate eligibility/omission | evidence_candidates.py, _evidence_selection_part01.py | context_selection.py, _project_context_service_part01.py, _evidence_selection_part03.py | B: remove risk-based decisions; DTO inert only |
| instruction_risk reason and metadata | proofability.py, evidence_models.py, domain/snippets.py | projection/SDK/MCP | B: remove semantic synthesis; inert wire compatibility allowed |
| metadata trust/permission | domain/trust_contract.py, model_visible_projection.py, _unified_context_service_part01.py, interfaces/mcp/context_tools.py | public consumers | B: preserve non-authorizing barriers; remove detector dependencies if found |
| samples/active public schema | mcp/_docs_server_resources.py, docs/mcp_footprint.py | source resources | B: align if changed; do not reinstall |

A exact allowlist: domain/content_trust.py; application/_action_packet_shared.py;
application/_action_packet_part01.py through part04.py; application/action_packet.py.
B exact allowlist: application/evidence_candidates.py; _evidence_selection_part01.py
through part04.py and _evidence_selection_shared.py; evidence_selection.py;
context_selection.py; evidence_models.py; _project_context_service_part01.py;
proofability.py; model_visible_projection.py; _unified_context_service_part01.py;
domain/trust_contract.py; domain/snippets.py; interfaces/mcp/context_tools.py;
mcp/_docs_server_resources.py; docs/mcp_footprint.py (all under docmancer/docs
unless mcp/ explicitly starts at docmancer/).

Additional production files require concrete symbol/caller evidence and coordinator
assignment, never parallel ownership. A/B may each add one small NEW test/shard and
one new handoff report. Old tests/gold/thresholds stay unchanged. Coordinator owns
this manifest, integration and final documentation. Reviewer C runs after integration.

## Preserved technical grammar / guards

filtering.py endpoint/format exclusions; source/hash/span/version binding;
finite/local membership, fetch transport, exact paths, protected/generated scope,
syntax parsing (Markdown, source imports, URI, API enums) and token budgets.
No claim that all regex anywhere in repo are semantic dictionaries.
No dictionary migration to prompts/config/metadata/LLM. Unknown authorization deny.

## Verification and exit

New addressable actual-consumer checks only: arbitrary prose preserved as quotes,
hostile risk/trust metadata cannot grant edit/workflow, no dangling imports/exports,
technical validation independent of deleted patterns. Inventory search extends to
production/templates/config to report concrete out-of-scope residuals honestly.
Full project EXIT only if surveyed scope supports it; installed artifacts UNKNOWN.
Workers hand off exact files, deleted symbols, hashes, checks and concrete blockers.

## Coordinator bounded wider inventory

Search production Python definitions/usages for synonym/morphology/stopwords,
NL risk/policy patterns, *_WORDS/*_TERMS/*_PATTERNS/*_KEYWORDS; AST literal tables
with >=8 strings and multiple prose strings; active packaged templates/config
searched for risk detector labels. No active packaged template match found.

Inspected non-owned suspicious names:
- core/_sqlite_store_part03.py::_strip_stopwords: generic tokenization only,
  no omission vocabulary.
- docs/curated_sources.py::_ecosystem_aliases: literal spelling only.
- domain/_answer_units_part02.py::_attribute_aliases: exact input only;
  inventory compatibility helpers return unresolved without NL recognition.
- domain/question_plan_core.py::_span_pattern: escapes exact supplied tokens;
  domain/context_windows.py::_source_unit_spans: punctuation/Markdown boundaries.
- source_map.py::_KEYWORDS/_GENERATED_MARKERS/_SECRET_ASSIGNMENT_RE:
  programming syntax/generated-file markers/credential redaction, not prose
  trust/intent inference. Preserve technical guard; no redesign in this pass.
- retrieval/query_planning.py, contextual_indexing.py, domain/query_terms.py:
  exact token/symbol/path grammar, not synonym/topic dictionary.
- _unified_context_service_shared.py::_LATEST_ALIASES and snippets language/version
  aliases: version selectors and code-fence language IDs, not NL synonym inference.
- frozen question probes/evaluation tables: diagnostics, not runtime classifier;
  unchanged, not an acceptance gate.

This is bounded source inventory, not an exhaustive proof of every external pack.
Final reviewer searches integrated definitions/callers for concrete missed remnants.

## Concrete wider remnants assigned to coordinator (disjoint A/B)

- retrieval/query_planning.py::_DOCUMENT_LOCATOR_RE: remove RU/EN locative-prefix
  dictionary; retain literal, bounded, unique source-path parsing only.
- domain/context_windows.py::_include_complete_code_fence: remove following/command/
  example word trigger; fence adjacency/closure and byte limit are structural.
- domain/_project_answer_contract_part01.py::_clean_phrase: stop English article
  omission; retain literal bounded spelling/punctuation handling.
- application/need_context_projection.py::precedence_context_variants: remove NL
  precedence boost; existing explicit relation/disposition remains context, not proof.
- application/_project_docs_service_shared.py + _project_docs_service_part01.py:
  remove PLACEHOLDER_PROJECT_DOC_RE and filename-dependent placeholder inference;
  empty-content validation remains technical, not a NL classifier.
- application/_patch_constraints_service_shared.py::ARCHITECTURE_DOC_RE: unused
  filename-family inference constant removed as part of old dictionary scope.

Coordinator alone owns these seven additional files and one new small test/shard.
No A/B file overlap; all included in final reviewer scope and effective manifest.

Coordinator new-only run: `tests/test_nl_dictionary_removal_literal_contract.py`,
17 PASS, normal conftest/offline. Actual helpers cover language-independent literal
path, ambiguity, structural fence/cap, preserved articles, nonempty placeholder-like
quotes, explicit precedence selection without verb scoring. Precedence fixture
patches upstream variant supply only, not the consumer under test.
Production syntax compiled in memory (385 modules); no imports/writes for this check.
Preservation snapshot outside repo: 1487 existing test/eval/guard files +13 frozen
manifest pins verified before execution. Recheck after integration/review.
AST literal regex inventory: 374 entries/101 files. Entries are not automatically
NL classifiers; dictionary removal concerns actual semantic decisions.

A handed off seven production files +small test/shard/report,12newPASS; integrated
with9/9payloadpins verified. Also removed semantic path-token density/behavioral
inference in action_packet.py (same A allowlist). No compatibility shim.
Concrete A-discovered consumers assigned coordinator: domain/evidence_qualification.py
and application/source_reference_evidence.py remove arbitrary raw risk-label veto;
retain actual identity/lifecycle/index freshness/path/scope restrictions. Typed source
taxonomy artifact/generated restrictions are not prose classifiers and remain.
New-contract small-budget observation (128 tokens) is recorded in A report; reviewer
must distinguish structural budget debt from NL deletion, not quietly waive it.

Coordinator follow-up addressable checks:2additional base nodes qualification
and reference catalog exercise fake risk labels while real identity/freshness/root
restrictions remain. Combined A+coordinator new-only run31PASS (12+19).
Removed symbols have zero production Python matches after A integration.
Only new test/shard evolved during this pass; all pre-existing tests unchanged.

Further direct substring inventory found callable legacy helpers in
docs/_patch_plan_context_part01.py (coordinator allocated): bottom/sheet/dialog
operation/goal/step inference, capability/Bluetooth/emulator rules, Flutter-word
verification inference. Removed six unused helper definitions/exports and topical
branch, no compatibility stubs. Public finite read-only implementation map and
scanner/source boundaries remain unchanged. Generic technical advisory risks remain.

docs/dartdoc.py also assigned coordinator: rank_dartdoc_seed_urls had an inline
English stopword omission set; deleted. Ranking remains literal URL-path/token
overlap and entity-page structure, no topic or synonym substitutions. Addressable
new test calls rank helper without fetch/network. Literal library/URL registry
discovery_candidates and ROOT_DOC_FILES diagnostic filenames are not NL dictionaries.

B integrated14files after13/13payloadpins check (11production+test+shard+report).
Raw risk flags/authority preferences removed from selector/normalizer/projectpart01,
source snippets/projector/trust/MCP alignment; structural proof and denial intact.
Coordinator assigned application/_project_context_service_shared.py: apply actual
literal artifact-path exclusions before caller risk/authority metadata; stop merging
caller risk labels into the exclusion decision. File/scope restrictions remain.
project_doc_ranking.py artifact/history path exclusions are preserved technical
source restrictions, not instruction-like prose detector or keyword exemption.
Explicit caller-provided forbidden terms/roles remain typed negative constraints,
not hand-maintained synonym/NL inference. Reviewer must inspect actual consumers.

Final C review found exactly C1/C2 (record immutable in
NL_DICTIONARY_REMOVAL_FINAL_REVIEW_RU.md): further inline stopwords/topical explanation
in coordinator patch shard and actual project_answer_outline topic coverage/reasons.
Coordinator removes C1 checks and C2 classifier/helper definitions entirely;
outline keeps literal bounded reading order with unknown coverage (empty map, not
false certified claims). Added two new actual-helper/outline nodes. No old tests
changed/run. Scope expanded by one file project_answer_outline.py. Narrow C rereview
required; prior43PASS does not itself waive these findings.

## Final closure

[NL_DICTIONARY_REMOVAL_CLOSURE_REVIEW_RU.md](NL_DICTIONARY_REMOVAL_CLOSURE_REVIEW_RU.md):
bounded source EXIT YES, C1/C2 closed,45newPASS,39/39payloadpins,1487/1487preservation,
13/13frozenpins,31changedproductionimports/385syntax PASS. Historical review BLOCKED
kept intact; corrected pins supersede only precise findings. No compatibility/quality/
release acceptance. Summary: [NL_DICTIONARY_REMOVAL_COMPLETED_RU.md](NL_DICTIONARY_REMOVAL_COMPLETED_RU.md).
