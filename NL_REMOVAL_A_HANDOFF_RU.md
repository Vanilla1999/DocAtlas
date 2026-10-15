# Agent A — удаление NL dictionaries, bounded handoff

2026-10-07. Только `/tmp/opencode/docatlas-removal-a-6e94d6ab`.
Baseline `6e94d6ab926f23c39c2bdbb7b926f6a1593ec68f`.
Implementation завершена в owned slice; independent integrated review PENDING.
**Full EXIT/security/quality/release acceptance НЕ заявлены.**

Прочитаны baseline `INERT_SECURITY_IMPLEMENTATION_RU.md`, `INERT_SDK_CLOSURE_RU.md`,
checkpoint `LOCAL_SECURITY_COMPLETED_RU.md`, `LOCAL_SECURITY_FINAL_INTEGRATED_AUDIT_RU.md`
и `FINAL_INTEGRATED_EXIT_AUDIT_RU.md` в
`v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/`.
Их historical retained-veto решения superseded только новым user removal request,
не переписаны и не объявлены current acceptance.

## Exact production files / symbols

Все пути application ниже относятся к `docmancer/docs/application/`.

1. `docmancer/docs/domain/content_trust.py`: удалены `_RISK_PATTERNS`,
   `detect_instruction_like_patterns`, их вызов, inferred flags и warnings.
   `annotate_context_pack` копирует caller metadata без классификации; отсутствие
   flags не синтезируется в safe result. `instruction_trust=untrusted_data`,
   `document_data`, non-executable boundary и original bytes сохраняются.
2. `_action_packet_shared.py`: удалён `_DANGEROUS_CONTENT_PATTERNS` целиком.
3. `_action_packet_part01.py`: удалены `_instruction_risk_flags`,
   `_content_instruction_risk_flags`, `_risky_source_keys`, их exports и все
   witness/fact eligibility checks. `_blocked_source_keys` сохраняет explicit
   rejected-source restriction, но не считает `sources.risky` блокировкой.
4. `_action_packet_part02.py`: удалён risk veto из `_authority_conflicts` и import;
   `_may_guide_workflow=False` сохранён. Generic NL word `lint` удалён из
   `_validation_bucket`, literal command names сохранены.
5. `_action_packet_part03.py`: удалены risk imports, code-target hints veto,
   selector risk omission accounting, item/fact/condition/snippet veto,
   risk omission counters/status text. Retrieved acceptance metadata больше
   не копируется в task acceptance policy. Quotes продолжают идти в cited
   `implementation_guidance`, не в execution/workflow permission.
6. `_action_packet_part04.py`: удалён special `risky_critical_source_facts`
   omission check; actual policy/workflow/trust denial и evidence fidelity остаются.
7. `action_packet.py`: удалены `_GENERIC_PATH_TOKENS`,
   `_TRUSTED_PROJECT_RULE_AUTHORITIES`, `_path_token_sequence`, `_path_tokens`,
   `_target_scope`, `_declared_authority_by_path`, `_behavioral_source_fact_contracts`
   и вызов inference. Path noun overlap/density больше не создаёт behavioral
   requirements. Удалён `_promote_trusted_behavioral_witnesses` no-op и вызов;
   нет replacement classifier/stub/renamed dictionary. Explicit caller
   public requirements, typed mutation DTO и formatter budget остаются.

## Remaining grammar / actual use

- Shared `_VALIDATION_START_RE`, `_UNSAFE_COMMAND_RE` → `_validation_command`:
  exact CLI syntax и metacharacter restriction, не prose authority. Builder не
  запускает команды; `_validation_bucket` reachable лишь через fact validation
  branch, которую `_may_guide_workflow=False` блокирует. Ни regex, ни bucket grant
  не дают. `_extract_facts` baseline inert adapter НЕ добавлен/заменён этим slice.
- `_SYMBOL_RE` → `_explicit_symbols`: identifier/qualified-name grammar для
  target/source attribution. Hash/evidence-id/schema regex → actual validators.
- `_requirement_witness` punctuation regex режет literal цитату на bounded spans
  для explicit term witness; не классифицирует intent/modality/risk. Word lists нет.
- Policy filenames `_SCOPED_POLICY_FILENAMES`, `.cursorrules`, literal copilot path
  → `_policy_scope`: root-bound filename attribution, никогда workflow trust.
- `_CODE_SOURCE_CLASSES`, authority/version/request enums и `_editable_target_path`
  literal filename/suffix exclusions → source/target routing restrictions, не NL
  inference. Catalog/root/module scope restrictions не расширены.
- Mandatory selection survival, assigned witness/source identity, evidence hash,
  current display hash/parent/span/version, explicit rejected source, stale checks,
  source identifier lengths и packet budget validators сохранены; no all-quotes
  drop / blanket unsupported replacement. Canonical prose остаётся manual-review,
  supporting bound prose остаётся quoted data.

## Tests / bounded execution

Добавлены только `tests/test_nl_dictionary_removal_packet_contract.py` (5 base nodes,
12 cases) и `tests/diagnostic_labels.nl_dictionary_removal_packet_contract.json`.
Normal conftest / reviewed behavioral labels, in-memory quotes/packets/projector,
temporary root только для attribution. Нет runtime index/providers/network.

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1
PYTHONPATH=/tmp/opencode/docatlas-removal-a-6e94d6ab
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python -m pytest
  -p no:cacheprovider -q --basetemp=/tmp/opencode/nl-removal-a-tests
  tests/test_nl_dictionary_removal_packet_contract.py
12 passed in 0.20s
```

Actual annotation сохраняет prose/caller risk metadata без детектора и без grants;
actual packet сохраняет supporting/canonical malicious-looking quote и version;
actual normalizer сохраняет hash/spans и отвергает malformed binding. Actual packet
и projection validators отвергают fake policy/workflow/trust/edit promotion.
Root escape remains unverified; 800-token bounded packet/oversize validator tested.
`git diff --check`: PASS. Старые suites/gold/floors/assertions не изменены и не запускались.

Первый new-test run: 10 pass / 1 fail при caller budget=128: compact packet estimate
231, больше 128. Compact failure body не изменялся этим slice; baseline differential
не выполнялся, поэтому это observed budget blocker, не доказанная baseline attribution.
Тест теперь отдельно проверяет usable 800-token budget и actual oversized denial;
невозможность fit минимальный 128-token schema budget НЕ объявлена исправленной.

## Outside ownership — B/parent closure required, НЕ редактировались

- `_evidence_selection_part01.py:159-161,467-468`: caller flags eligibility/omission
  (`instruction_risk`). `evidence_candidates.py:165-174,313` собирает labels;
  `_evidence_selection_part03.py:144`, `evidence_models.py:22,335`, `proofability.py:24`
  сохраняют DTO/reason labels. Пока selector veto существует, flagged quote может
  не попасть в packet. New tests не утверждают обратного и не stub-ят selector.
- `context_selection.py:47`, `_project_context_service_part01.py:443-453,512-513,571`,
  `domain/evidence_qualification.py:163`, `source_reference_evidence.py:50`:
  outside risk-dependent checks. `domain/trust_contract.py` и
  `_project_context_service_shared.py` risk taxonomy/selected/rejected/risky assembly;
  explicit source restrictions нельзя безусловно смешивать с NL detector debt.
- `domain/snippets.py:259-292,498`, `interfaces/mcp/context_tools.py:247-281`,
  `_project_docs_service_part03.py:721`: labels propagation/merge. Version mismatch
  (`not_exact_version`), stale/current identity и root restrictions должны выжить B cleanup.
- CLI/resources/eval/project-tools/Unified part02 также отображают risky DTO data;
  не authenticated source/execution permission. Installed wheel/index/external SDK
  parity UNKNOWN. Direct references к удалённым detector/helper definitions вне
  owned production файлов не найдены; historical tests могут их импортировать,
  compatibility shim запрещён и не добавлен.
- 128-token compact-budget observation выше — integrated parent triage, не permission
  расширить production ownership. Independent review после A+B integration обязателен.

Нет agents, commits/push, PRIMARY edits, install/link, bytecode, index work или
изменений frozen reports/tests. Shared venv только использован абсолютным путём.

## SHA256 payload pins (report без circular self-pin)

```text
a8f7d738a66b55a30e0c4ab6a0694a647f1500f1cbfb15e74896daea8fbba3b5 docmancer/docs/domain/content_trust.py
f4e6fe9af9940598d9a6cdb96175fbe497eb13e55e932bc39d50294b060706fc docmancer/docs/application/_action_packet_shared.py
948f5298cdf4af1882b33bdf5b145b98aea05e5697c3030e36d5e3c1fce3770d docmancer/docs/application/_action_packet_part01.py
660671f9e3e2aa1ea4b097ca6844d07828f70e59e1d12a6b9d5bd9b276935372 docmancer/docs/application/_action_packet_part02.py
acd5356da296fbb943818cea5158864bebbd6a1a4b033f88004120a9e0c8adbb docmancer/docs/application/_action_packet_part03.py
3cbb18d718e91bfdab0238e80ba2ca4d44ba9a6e69e22c8268413b6277a0b1b5 docmancer/docs/application/_action_packet_part04.py
7155a5e07818e5af1456d015004f6462c90cb2cc638b162ac89eb441724ac2ce docmancer/docs/application/action_packet.py
48e43caf812a9b6f1cb84eedb106ea3d3e8a41823be9b3d730227f4c1c1a0f1a tests/test_nl_dictionary_removal_packet_contract.py
53b5f6e09cfc5350549b0ffc41e5650c50783204ac11c995c7b5f3663c009505 tests/diagnostic_labels.nl_dictionary_removal_packet_contract.json
```
