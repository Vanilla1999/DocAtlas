# P0 slice 3: patch/source/discovery и bridge paths

2026-10-06. **P0 ACTIVE**, production/tests не изменялись.
Результаты ниже — source inspection и synthetic helper probes, не доказательство
полного end-to-end recall и не независимое review.

## D25: concrete surface rules

`question_plan.py` импортирует frame matchers, normalization, component rewrites и
`question_plan_surface_rules`; `_RULES` задаёт порядок распознавания. Это не путь,
независимый от словарей после удаления D01.

Подтверждённые дополнительные S / REMOVE semantic rules:

- `question_plan_surface_rules.public_tools_with_purposes:208–225`: общему вопросу
  назначаются три known `_PUBLIC_TOOLS` как facets без source inventory. Tool schema
  enum может оставаться в protocol, но не должен подменять найденный inventory.
- `python_version_support:229–244`: вопрос без названного продукта получает
  `subject="DocAtlas"`. Subject должен связываться с текущим project/source, а не таблицей.
- `public_tool_usage:189–205`: matching только трёх известных tool names. Literal
  extraction должно работать с unknown symbol; schema validation отдельно.
- `mcp_request_handling`, `provider_request_timeout`: закрытые NL surface templates.
- `question_plan._release_docs_line_limit:76–95`, `_storage_coordination_contract:98–120`:
  special topic→relation plans. Значения/контракты извлекать из source, не гарантировать
  их существование одной формулировкой вопроса.

`governance_value_proof._android_requirement_is_bound:264–317` (D25): при context,
содержащем `android 13`, применяется `_ANDROID_13_RE` и special active/passive order
checks. **S / SPLIT**: заменить platform-specific handling общим subject/context/
predicate binding; сохранить polarity/direction negative controls. Не удалить guard
как будто он только ranking boost.

Все remaining frame symbols ещё не классифицированы: D25 не DONE.

## D29/D30: patch dictionary дублируется inline

| Symbol / caller | Source mechanism | Decision |
|---|---|---|
| `_patch_constraints_service_part02._task_terms:459–486` | `PHRASE_ALIASES`, open/close/... verbs, local `stop` list добавляют/фильтруют search terms | D29 S/REMOVE aliases; D30 S/SPLIT inline NL filters. Literal quotes/current-source symbols отдельно. |
| `_term_variants:499–512` | Aliases + синтетические camel/snake/compact variants | D29 S/REMOVE semantic expansion; technical spelling transformations требуют контроля точной identity, не автоматического proof. |
| `_is_asset_related_task:597–599` | Любой substring из `ASSET_TASK_TERMS` назначает asset task | D30 S/REMOVE NL trigger; generated-source metadata отдельно. |
| `_symbol_from_line:550–575` | `GENERIC_CALL_SYMBOLS` отбрасывает known calls; прочие declaration/call regex | D30 S/SPLIT library-symbol blacklist vs structural source parser. Последний non-generic call не даёт ownership proof. |
| `_patch_review_service_part02._task_symbol_tokens:455–479` | Inline quick info/быстрая информация → openinfo; закры*/штор*/close menu → closemenu; scan/скан → gotoscandocinit | D29/D30 S/REMOVE: самостоятельный дубль, не consumer `PHRASE_ALIASES`. |
| `_is_low_value_symbol_candidate`, `_has_only_low_value_symbols`, `_has_low_value_matched_symbol` | Known `LOW_VALUE_SYMBOLS` снижают значение кандидатов, explicit spelling override | D30 S/SPLIT blacklist; import/export source syntax отдельно. |
| `patch_constraint_validation_service._line_has_decision_shape`, `_line_adds_policy_decision`, `_policy_diff_evidence:342–379` | Policy keyword lists и guessed variable names вместе с branch/operator parsing | D30 S/SPLIT: сохранить запрет выдавать unknown ownership за satisfied; semantic policy guesses заменить source/task-derived constraints. |

`POLICY_KEYWORDS` объявлена, но grep по production tree не нашёл consumers кроме
declaration. Это **static unused candidate**, не доказательство runtime dead code:
bridge exports/внешние consumers нужно проверить перед удалением.

## D31: code navigation

- `code_context._LOW_SIGNAL_TERMS` фильтрует NL question; `_GENERIC_SOURCE_TERMS`
  участвует в `generic_only` (`229`) и relevance (`271`). **S / REMOVE semantic lists**
  после regression checks. Unknown module/symbol должен находиться без named-topic policy.
- `source_map._QUERY_STOPWORDS` → `_query_terms:764–773`: фильтрует free-form query,
  но отдельно оставляет quoted text. **S / SPLIT**, literal path/quotes и общий cap 24 сохранить.
- `source_map._KEYWORDS` → symbol/reference extraction (`643,678`): reserved programming
  words не считать identifiers. **S / technical-retain candidate** для source syntax,
  не NL routing. Подтверждение корректности по поддерживаемым source languages ещё нужно.
- Source suffixes, under-root checks, byte/file/hop limits — отдельные boundary contracts.
  Не ослаблять их вместе с фильтрами слов.

## D32: explicit registries, не topic translation

- `discovery_candidates_for` нормализует **library input**, затем exact tuple lookup;
  без ecosystem ищет тот же normalized library key. Не делает substring topic matching.
- `_canonical_ecosystem` задаёт pub/flutter/dart→dart — explicit ecosystem alias;
  это proposed technical normalization, не RU/EN interpretation вопроса.
- Caller `_library_docs_service_part01:163–170` использует candidates при отсутствии
  registry record. Одна candidate URL не доказывает exact snapshot и не authorizes answer.
- `dart_official_docs.DART_PACKAGE_OFFICIAL_DOCS` разрешает package identity в seed URLs.
  `curated_source_for:168–181` проверяет library/ecosystem и не принимает unversioned
  source для exact dependency request; `curated_target_spec:188–193` допускает verified seeds.

Решение **S / SPLIT / proposed technical retain**: оставить exact identity→source registry
при сохранённых URL/version/fetch gates; не использовать confidence labels как evidence proof.
Не утверждается свежесть всех hardcoded URLs. Network проверки в этом slice не выполнялись.
Technical exception требует записи/согласования P1, D32 не закрыта автоматически.

## Bridges: проверять public entry, не только shard import

`_internal/shard_compat.py` устанавливает public wrappers через generated `exec`.
До вызова wrapper sync копирует совпадающие имена public facade в shard globals.
Поэтому source grep и monkeypatch private shard могут не отражать фактический вызов:
public facade способен вернуть старое значение при следующем sync.

`patch_review_service.py:17–25`, `patch_constraints_service.py` используют class bridge.
Diagnostic probes вызвали **public classes**, не shard classes; output содержит wrapper
global module, unwrapped implementation module и bridge marker.

`docs_context_projection.py:63–82` имеет другой механизм: dynamic facade hooks передаются
в core для selection/coverage/requalification. При P2 tracing использовать эти hooks
и фиксировать final crop; патч alias builder не покрывает все collaborators.

`project_answer_contract.py` импортирует shared/part01/part02 wildcard и сохраняет
legacy builder отдельным alias. В bridge/producer map необходимо учитывать все три
shards и public override, а не считать public file единственной implementation.

Этот source review не закрывает installed distribution audit, который остаётся OPEN.

## Evidence и checks

Runner: [p0_neighbor_probes.py](p0_neighbor_probes.py).
Report: [archives/p0-neighbor-probes.json](archives/p0-neighbor-probes.json).

```bash
PYTHONPATH=. .venv/bin/python v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/p0_neighbor_probes.py
.venv/bin/python -m pytest -q tests/test_patch_constraint_symbol_grounding.py tests/test_patch_constraint_validation_service.py tests/test_library_discovery_candidates.py tests/docs/test_source_map.py tests/docs/test_curated_sources.py
```

- Probes exit 0; confirm inline symbol injection и exact discovery lookup:
  `fastapi`/`FASTAPI` дают candidate; `fastapi server`/unknown library — нет.
- Existing subset **76 passed in 1.03s**, exit 0.
  [Лог](archives/p0-neighbor-baseline-pytest.log). Это не required full CI.
- Product source SHA256 проверяется относительно первого static manifest.

## Next

Сформировать P1 decision ledger (numeric normalization, exact registries, schema enums,
alias-specific tests), завершить remaining frame/config/package audit. P0 пока ACTIVE;
нет основания объявлять 34 группы полностью разобранными или replacement готовым.
