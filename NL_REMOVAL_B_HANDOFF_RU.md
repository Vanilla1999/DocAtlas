# Agent B: удаление NL-classifier consumer effects — bounded handoff

2026-10-07. Только `/tmp/opencode/docatlas-removal-b-6e94d6ab`.
Baseline: `6e94d6ab926f23c39c2bdbb7b926f6a1593ec68f`.
**Реализовано в owned surfaces. Parent review PENDING; full EXIT НЕ заявлен.**

Прочитаны baseline root `INERT_SECURITY_IMPLEMENTATION_RU.md`,
`INERT_SDK_CLOSURE_RU.md`, checkpoint `LOCAL_SECURITY_COMPLETED_RU.md` и
`LOCAL_SECURITY_FINAL_INTEGRATED_AUDIT_RU.md`. Их исторический retain-veto status
не переписан; новый slice выполняет явный запрос удаления consumer effects.

## Изменённые symbols / контракт

- `evidence_candidates.normalize_candidates`: caller `risk_flags` и
  `instruction_risk_flags` больше не агрегируются в eligibility. Неиспользуемый
  `risk_flags` helper/export удалён; внешних production callers не найдено.
  `EvidenceCandidate.instruction_risk_flags=()` — существующий inert DTO slot,
  не detector и не grant. Original row/quoted bytes сохраняются.
- `_evidence_selection_part01._candidate_window_valid`, `_eligible_candidates`:
  сняты risk-label veto и trust-contract `risky/rejected` source-label veto,
  canonical-classifier source-class exclusion и canonical stale critical promotion.
  Удалён неиспользуемый `_trust_source_keys`/export. Сам stale veto остаётся.
- `_candidate_preference`, `_assignment_preference`, `_repair_mandatory_selection`,
  `_marginal_utility`, part02 `_reserve_and_select`, `_selected_feature_trace`:
  удалены authority-label preferences/boosts/penalties; technical version,
  exact snapshot, coverage, literal symbols, cost/rank/caps сохранены.
- part02 `_authority_conflicts` и part03 его invocation/missing/reason branch
  удалены: distinct quoted bytes + canonical label больше не создают presumed
  incompatibility. `_with_coverage` не выдаёт `project_rule` proof по authority
  metadata: normative authorization остаётся unknown/denied. Structural
  `code_group` и scope assignments не заменены blanket unsupported.
- part03 `select_evidence`: risk metadata/trust contract не включаются в
  eligibility hash; risk slot исключён из candidate trace. Неиспользуемый
  `_canonical_contract_value`/export удалён. Hashes остальных identity/assignment
  inputs остаются проверяемыми; authority attribution может оставаться в trace,
  но не выбирает, не veto-ит и не даёт permission.
- `context_selection.component_witnesses` и project service part01
  admissible/observed/rescue candidates: удалены risk-label branches. Rescue
  remains inert при baseline `missing_component_queries=()`; не включён заново.
- `model_visible_projection.project_docs_answer`: удалён вызов combined
  `evidence_policy_rejection_reason`. Его реальные technical проверки сохранены
  явно: project identity/mismatch, stale/freshness, synchronized index,
  `lifecycle_allows`. Risk labels/semantic forbidden-term taxonomy не выполняются.
- `proofability._ELIGIBILITY_REASON_ORDER`: удалён retired `instruction_risk`.
- `trust_contract.build_project_context_trust_contract`: selected-source taxonomy
  risk flags больше не экспортируются. Technical stale/version diagnostics и
  `direct_webfetch=forbidden`, inert source dimensions сохранены.
- `snippets._snippet_payload`: risk flags и synthesized risk flag fallback удалены;
  version fallback/exactness остаются отдельной technical binding. Caller trust /
  content-boundary claims не echo-ятся как scoped policy: top-level/document_data
  `instruction_trust=untrusted_data`, `executable_policy=False`.
- MCP `_align_trust_contract_with_snippets`: переносит только version binding /
  exact-version match, не risk metadata. Existing MCP read-only request parsing и
  SDK/projection edit denial не ослаблены.

Новые dictionaries, LLM/detector stubs, prompt/metadata relocation, grants,
broker/dispatcher не добавлены. Source child/parent/display digest/span/version,
root/membership, freshness/lifecycle, source/window/token caps не удалены.
DTO omission enums и authority provenance — wire/attribution, не NL classification.
Machine grammar regex (fences, identifiers, SHA256, spans, code syntax), exact
literal query matching и version enums не удалены как якобы NL dictionaries.

Allowlist inspected but unchanged: `_evidence_selection_part04.py`,
`_evidence_selection_shared.py`, `evidence_selection.py`, `evidence_models.py`,
`_unified_context_service_part01.py`, `mcp/_docs_server_resources.py`,
`docs/mcp_footprint.py`. Их существующие inert barriers/static samples сохранены.
A-owned `content_trust` и все `action_packet` shards НЕ редактировались.

## Проверки

Единственный новый module:
`tests/test_nl_dictionary_removal_consumer_contract.py`; отдельный diagnostic shard,
normal conftest, основной manifest неизменён. 3 base nodes / 8 cases:

- Actual normalization + selector + public `project_docs_answer`: EN/RU/ZH
  instruction-like quotes сохраняются; fake risk/trust labels и risky/rejected
  contract не veto-ят structural assignment. Competing canonical-labelled quote
  не получает преимущество над mechanically preferred supporting row.
- Invalid display digest, missing parent, inverted span, missing stable child
  всё ещё дают `invalid_identity`, даже с fake issuer/consent/authorization.
- Actual Unified SDK и public answer projector: caller `edit_ready=True` и trust
  claims не дают edit/workflow grant; bound original quote/version/snapshot и
  публичный 800-token ceiling сохраняются.

Final executed command:

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 PYTHONPATH=/tmp/opencode/docatlas-removal-b-6e94d6ab /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest -p no:cacheprovider -q --basetemp=/tmp/opencode/nl-removal-b-test-final tests/test_nl_dictionary_removal_consumer_contract.py
8 passed in 0.42s
```

Earlier own-test runs: три `7 passed / 1 failed` при попытке public MCP read-context
с `risk_flags`: context unavailable из-за outside-allowlist residual ниже. Это
НЕ закрытый MCP result. В финальном module проверяется owned public answer
projector напрямую, а не утверждается, что этот MCP blocker исправлен.
Ещё один `7 passed / 1 failed` выявил оставшуюся ссылку на удалённый
`conflict_review_required`; ссылка исправлена до final run. Последовательные
temporary basetemps уникальны; существующие файлы не очищались.
`git diff --check`: PASS. Existing tests/gold/floors/thresholds НЕ менялись и
НЕ запускались ради compatibility. Full-suite/quality acceptance UNKNOWN.

## Outside-allowlist dependencies — parent должен закрыть, здесь НЕ редактировались

1. `docs/domain/evidence_qualification.py::evidence_policy_rejection_reason:163-179`:
   `risk_flags -> unsafe_evidence`; caller/probe `forbidden_evidence_terms` и
   `forbidden_catalog_roles` дают semantic veto. Actual other callers:
   `application/joint_context_candidates.py:65-69`,
   `joint_context_selection.py:113`, `context_query_probes.py:108-112`,
   `need_context_projection.py:83`; read-context projector находится в
   `docs_context_projection.py` / `_docs_context_projection_core.py` и использует
   эту цепочку. Owned `project_docs_answer` больше не делегирует combined helper,
   но MCP project-only docs_context всё ещё blocked для fake risk labels.
2. `application/_project_context_service_shared.py:155-164,342-345`: taxonomy и
   metadata risk flags агрегируются; `_should_skip_low_trust_project_source`
   исключает risk/authority-labelled rows до owned selector. Это реальный
   upstream consumer, не inert wire slot.
3. `application/source_reference_evidence.py:50`: metadata risk flags ещё veto-ят
   reference evidence; `domain/project_doc_ranking.py:66-84` ещё производит
   artifact risk taxonomy. Их removal требует владельца вне текущего allowlist.
4. `application/_unified_context_service_part02.py:459-473` ещё экспортирует
   technical stale/warning risk labels. Сами labels не объявлены execution grant;
   parent должен проверить remaining consumers после closure пунктов 1–3.
5. A-owned detectors/content annotation/action packet ожидают отдельную интеграцию
   A. Здесь не заявляется их удаление или полный dictionary-free runtime.

Installed wheel/packs/index/stdio/external SDK parity не проверялись/не менялись.
Нет index build/write/rebuild, live network/providers, reinstall/dependency installs,
primary edits, новых agents, commits/push. Full EXIT только после parent review и
actual outside-consumer closure; этот handoff не waiver blockers.

## Exact changed files / SHA256

Ровно 11 production updates + 1 new test + 1 new shard + этот new root report
(14 paths). Report не self-pin-ится, чтобы избежать circular hash.

```text
a722a5eec66621a77b0d6f6eee796a30e731412f36e0bb39a7b71a2e4635748c docmancer/docs/application/_evidence_selection_part01.py
eb1ed3f6375256cc053057473c6b9804f64d061974b1b82d6c56d9e9f403f7a9 docmancer/docs/application/_evidence_selection_part02.py
2fdd9f51198ebc1f80a2bc58e59a13244a45168186fa16547fe2fcbfc5454775 docmancer/docs/application/_evidence_selection_part03.py
2f74a7ac43edbc8f9c61aa164b05f24b906d7726c911205997852661f8ea1d40 docmancer/docs/application/_project_context_service_part01.py
d9fe87fb461059ee0f0113d474393da2e285815d3d4cdf67067f73431c870259 docmancer/docs/application/context_selection.py
326093dd9f08553d1e10d97af0b284148003247e8401d17273342a50a60a91f7 docmancer/docs/application/evidence_candidates.py
d8fd0509399c51fe536bd4024cacfea51d9aa493ad223acf190d5d34df329f20 docmancer/docs/application/model_visible_projection.py
b997fc57cae0fb9f212fcde7d24ba08c5ac88d7a7d54ab1736614a83ae2a2d8d docmancer/docs/application/proofability.py
c1ec274488737d95b36bd0b12afdc9125b0f3ccf4c3d97a645af9acde761f6ae docmancer/docs/domain/snippets.py
d60504ee4fc9b5b00f4c04a866216c2a4640f717eff0f94ef6482a4864936cf9 docmancer/docs/domain/trust_contract.py
ea603ad3742ee26c4a23118df947d738920a3c899cfe725def769a32079b85c6 docmancer/docs/interfaces/mcp/context_tools.py
3309731c973c75461e0dc31ec8ab14a436d5e6a898af3f290d9a5d92d7bb690d tests/diagnostic_labels.nl_dictionary_removal_consumer_contract.json
c505602f6feda95902d0a8e60981cdd088d5904533e70b25040e10fb47f9769b tests/test_nl_dictionary_removal_consumer_contract.py
```

Report path: `NL_REMOVAL_B_HANDOFF_RU.md`.
