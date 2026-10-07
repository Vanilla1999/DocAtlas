# Независимый финальный review C — NL dictionary removal

2026-10-07. Primary `/home/viadmin/StudioProjects/hermes/docmancer`, branch
`integration/stage3-v2-identity-pr1`, baseline
`6e94d6ab926f23c39c2bdbb7b926f6a1593ec68f`.

## Вердикт: BLOCKED

Интегрированное удаление A/B/coordinator и новые consumer contracts проходят,
но **физическое удаление старых NL dictionaries и зависимых ветвей не завершено**.
Найдены конкретные действующие/вызываемые остатки ниже. Это не требование вернуть
legacy behaviour. Минимальные production-файлы для исправления: **ровно два**:

1. `docmancer/docs/_patch_plan_context_part01.py`.
2. `docmancer/docs/application/project_answer_outline.py`.

Reviewer не изменял source/tests/config/manifest/historical reports. Единственный
новый repository artifact — этот отчёт. Subagents/install/network/providers/runtime
index mutation/full CI/legacy suites/current 95-failure triage не выполнялись.

## Конкретные blockers

### C1. Inline English omission dictionaries и topical helper branch

`docs/_patch_plan_context_part01.py:190–223`:

- `_ordered_terms` сохраняет ручной список
  `plan/change/changing/changes/with/and/the/for/from/into` и `continue` по нему.
  Реальный caller: `_patch_plan_context_part02.py:131`
  `discover_relevant_source_files`; далее terms влияют на variants/score.
- `_looks_like_symbol` сохраняет второй список
  `plan/use/using/change/changing/changes/with/and/the/for/from/into/find/semantics`.
  Caller `_probable_symbol_terms`; оба helpers доступны через `__all__` и shard
  exports. Даже отсутствие live discovery caller не означает физическое удаление.
- `_nearest_dependency_alternatives:251` сохраняет отдельную ветвь
  `"bottom" in symbol_tokens & api_tokens`, синтезирующую объяснение
  `Closest resolved dependency API for bottom sheet behavior.` Helper экспортирован.

Новый in-memory вызов на текущем source, без scanner/index/network:

```text
_ordered_terms('PLAN CHANGE MARBLE', []) -> ['MARBLE']
_looks_like_symbol('PLAN') -> False
_looks_like_symbol('MARBLE') -> True
_nearest_dependency_alternatives('BottomSheet', [{'symbol': 'BottomPanel'}])
  -> reason: Closest resolved dependency API for bottom sheet behavior.
```

Это NL omission/topic inference, а не identifier grammar: `PLAN` и `CHANGE`
проходили бы одинаковую uppercase structural проверку с `MARBLE`, но вырезаются
по English vocabulary. Минимальное исправление — удалить два vocabulary checks
и topical reason branch; сохранить реальные identifier/path/source-boundary guards
и generic alternative attribution. Не добавлять synonym replacement или shim.

### C2. Actual answer-outline consumer продолжает классифицировать prose coverage

`application/project_answer_outline.py:64–74::compute_coverage` объединяет
`path/title/heading_path/content` и выдаёт topic booleans через ручные NL phrases:
`overview/what you get`, `project structure/layout`, `install/setup`,
`action packs`, `breaking/added` и др. Это не проверка API syntax или membership.

Actual caller: `build_project_answer_outline:41`; production caller:
`_project_context_service_part01.py:620`; результат сохраняется в answer outline.
Ручной vocabulary перемещён не был — он уже остаётся в действующем consumer.

Новый in-memory вызов:

```text
compute_coverage(context_pack=[{'content': 'overview layout install added'}])
  -> high_level_overview=True, project_structure=True,
     setup_or_commands=True, release_history=True
```

Никакой bound claim/proof для четырёх тем здесь нет. Labels диагностические и
не дают edit permission, но strict dictionary-removal goal включает такие
topic classifiers, а не только security detectors.

В этом же файле `reason_for_source:53–58` угадывает topic по substring
`architecture` в filename и `mcp` в heading/path. Actual call для
`docs/myarchitecturefiction.md` с unrelated content выдаёт
`Best internal architecture and pipeline source.` Это положительная topic/preference
аннотация, не техническое запрещение artifact path. Удалить topic-derived coverage
и эти inferred explanations; оставить literal source attribution/read-order limits.
Не заменять всё на unsupported и не удалять сами цитаты.

## Подтверждённая integrated часть

Прочитаны removal manifest и оба root handoffs; просмотрены baseline diff всех
**30 production-файлов: A7 + B11 + coordinator12**. Inventory текущих definitions,
callable helpers/exports включал AST regex alternatives/word boundaries и literal
collections, risk consumers и прямые symbol references по `docmancer/`.

- Удалённые risk detectors/helpers и coordinator placeholder/operation helpers
  отсутствуют в production search; dangling references к этим names не найдены.
- Current annotation сохраняет original document bytes/caller metadata, но всегда
  задаёт `untrusted_data`/non-executable boundary. `_may_guide_workflow=False`.
- Actual normalizer/selector сохраняет quoted bytes, child/parent identity,
  display/snapshot digest, char/line spans и version. Raw risk flags и authority
  preference больше не veto/boost; malformed bindings продолжают отклоняться.
- ActionPacket сохраняет supporting/canonical quoted guidance, не переносит
  retrieved acceptance metadata в task policy; forged policy/workflow/trust
  отклоняются реальными validators. Отсутствие detector hit не даёт permission.
- Новые actual Unified SDK/public projector/MCP проверки сохраняют bound quote,
  `edit_ready=False`, `cite_only`; fake issuer/consent не превращают read в mutation,
  public MCP передаёт `allow_network=False`, mutation operation `none`.
- Qualification/reference catalog raw risk veto снят. Identity/freshness/lifecycle,
  root escape, snapshot и scoped membership остаются самостоятельными guards.
- Upstream `project_context_pack:155–163` применяет literal artifact-path taxonomy
  **до** caller authority/risk attribution. Caller risk не влияет на exclusion.
  Artifact/history path exclusions — технические negative boundaries, не C2.
- `forbidden_evidence_terms/forbidden_catalog_roles` в qualification — явные caller
  negative constraints; не hand-maintained inferred vocabulary и не positive grant.
- Existing CLI syntax, programming keywords, version/API enums, fence/language IDs,
  punctuation windows, tokenizer grammar и credential-assignment redaction не
  классифицированы как NL dictionaries. DTO inert risk slots не detectors.

Active config inventory: root `docatlas.yaml`, `docatlas.docs.yaml`,
`docatlas.project-docs.yaml`, `server.json`, packaged `support_surfaces.json` и
`docs/curated_sources.json`; package non-Python template/config glob вернул только
два JSON. Relocated detector tables/labels в этих config не найдены. Packaged Python
templates/resources попадали в source inventory. Это bounded search, не доказательство
отсутствия всякой semantic logic во всех external artifacts.

## Новые проверки и preservation

Normal conftest, offline, только три NEW modules:

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1
PYTHONPATH=/home/viadmin/StudioProjects/hermes/docmancer
.venv/bin/python -m pytest -p no:cacheprovider -q
  --basetemp=/tmp/opencode/nl-removal-c-final
  tests/test_nl_dictionary_removal_packet_contract.py
  tests/test_nl_dictionary_removal_consumer_contract.py
  tests/test_nl_dictionary_removal_literal_contract.py
43 passed in 0.65s (12 + 8 + 23)
```

- Effective integrated SHA256 pins: **38/38 MATCH**, до/после проверок.
- `/tmp/opencode/nl-removal-preserved-files.json`: **1487/1487 MATCH**, до/после.
  Старые tests/eval/gold/thresholds/technical guards не изменены.
- `archives/p1-approved-freeze-manifest.json`: independently rehashed owner,
  reference, review, seven reviewed inputs, two reference files и migration ledger:
  **13/13 MATCH**. Их historical acceptance не переинтерпретируется.
- Production compile in memory: **385 modules PASS**; imports всех изменённых
  **30 production modules PASS**, declared `__all__` symbols существуют.
- `git diff --check`: PASS.
- C1/C2 examples — новые прямые in-memory helper calls, не legacy tests.

## 128-token budget: существующий structural debt, не removal regression

`_compact_failure_packet` и `_fit_packet` в `_action_packet_part02.py` сравнили
по `ast.dump` с `git show 6e94d6ab:<path>`: **оба AST неизменны**.
Текущий `build_action_packet(question='reference', context_pack=[], max_tokens=128)`
возвращает `estimated_tokens=231`, `status=insufficient_evidence`.
`validate_action_packet(packet, max_tokens=128)` реально отклоняет его:
`estimated_tokens mismatch or hard limit exceeded`.

Следовательно, schema-minimum 128 не обеспечивается compact formatter даже без
источников: это сохранённый structural budget debt. Сам formatter oversize не
исправлен; guard rejection не означает, что builder всегда fit-ит бюджет. Новые
800-token packet/public checks PASS. AST equality не является whole-baseline runtime
differential и не доказывает все исторические token outcomes. Эта проблема не
превращена в waiver или новый NL-removal blocker; полный budget/release claim запрещён.

## Границы EXIT

**Source semantic EXIT сейчас BLOCKED ровно C1/C2 в двух указанных файлах.**
Parent может исправить эти минимальные remnants и предъявить изменённые файлы/
обновлённые pins для узкой rereview, без восстановления legacy expectations.
Новые 43 PASS не покрывают C1/C2 и не отменяют физический inventory blocker.

Installed wheel, external packs/SDK deployments, current runtime index и live
stdio parity — **UNKNOWN**, не изменялись. Full quality/release/full-security
acceptance не заявлены; текущие старые failures не исследовались.

Finding source SHA256:

```text
01eb8aae5e1b1f9965634eca96bce982aad91d3118a839170d9e638365b6e325 docmancer/docs/_patch_plan_context_part01.py
c90e9e1bbe154ee0a7e17519258392dc714446bcfdfcc644a8ad7f2c9a6c4ef5 docmancer/docs/application/project_answer_outline.py
```
