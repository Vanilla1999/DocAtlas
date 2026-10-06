# Реестр ручных словарей и связанных правил

Дата: 2026-10-06. Основа: `8d2381d8c9d18498483feaaab918d93dfee47969`.
Рабочее дерево дополнительно содержит удаление `instruction_trust` block.
SHA-256 текущего `project_retrieval_intent.py`:
`ddbaa54285e315c8267c1a1c3db3827b53b68e365991a4119805801c9751505e`.

План выполнения: [DICTIONARY_EXIT_PLAN_RU.md](DICTIONARY_EXIT_PLAN_RU.md).
Проверенные A/B: [RETRIEVAL_DICTIONARY_REVIEW_RU.md](RETRIEVAL_DICTIONARY_REVIEW_RU.md).

## Как читать отметки

- **M** — влияние измерено A/B; это не означает, что удаление безопасно.
- **S** — механизм подтверждён чтением кода; причинное влияние на качество ещё не измерено.
- **C** — кандидат обнаружен статическим поиском; нужен разбор потребителей/достижимости.
- **REMOVE** — убрать ручное семантическое правило после проверки замены.
- **SPLIT** — смешаны семантическая эвристика и технический контракт; разбирать по символам.
- **REVIEW** — принять поэлементное решение, не удалять автоматически.

Сейчас все строки имеют implementation status **OPEN**, кроме локального удаления
одного блока D01, которое имеет статус **CANDIDATE / recall regression**.
Пометки находятся в этом реестре: production-файлы массовыми TODO не изменялись.

## Область и полнота поиска

Выполнен AST scan всех **383 Python-файлов `docmancer/`**, без ошибок разбора:
строковые dict/set/tuple/list и присваивания с 8+ строковыми константами.
Дополнительно выполнены regex/text searches по aliases, intents, concepts, stems,
`audited_rewrite`, `startswith(stem)` и чтение потребителей. Малые inline rules и
словарные regex найдены отдельным чтением; AST threshold не служит доказательством
их отсутствия. Поиск обнаружил правила также в `core/`, `retrieval/` и `mcp/`.

Это **первичный реестр, не доказательство полноты**. Конфигурации, templates,
генерируемые artifacts, prompts и packaged paths ещё требуют полного обхода на P0.
В каждом следующем diff реестр обновляется по символам и фактическим call paths.
Номера строк — ориентиры текущего tree; после правок ориентироваться на символы.

## A. Поисковые подстановки и routing

### Дополнение scope после frame/package baseline audit

| ID | Статус / действие | Механизм и потребитель | Граница миграции |
|---|---|---|---|
| D35 | S / SPLIT | `docmancer/docs/domain/context_request_preferences.py`: `recognized_request_parts`, `direct_evidence_preference`, `recognized_request_satisfied`; EN example/signature/timeout и `_TIMEOUT_KINDS` влияют на selection и stopping | Убрать ручную смысловую интерпретацию; сохранить code syntax, budgets и partial context. |
| D36 | S / SPLIT | `docmancer/docs/application/evidence_semantic_density.py`: `_BEHAVIORAL_FACT_RE`, `_HARD_NORMATIVE_RE`, `_GENERIC_IMPLEMENTATION_RE`; patch evidence selection/scoring | Normative lexical ranking заменить без потери condition/negation binding; config syntax выделить отдельно. |
| D37 | S / SPLIT | `docmancer/docs/domain/question_ownership.py:FROZEN_OWNERSHIP_CASES` → `FROZEN_LEGACY_QUESTIONS` → `evidence_requirements.py:455` | Test-like exact question registry достижим в production arbitration. Не переносить вопросы в новый registry; ownership tests мигрировать только по согласованному ledger. |
| D38 | S / SPLIT | `connectors/fetchers/pipeline/filtering.py:_ROOT_HINT_SEGMENTS`, `_LOCALE_PREFIXES`, `_BLOCKLIST_PATTERNS`, `_STRIP_PARAMS`; `fetchers/github.py:_DEFAULT_EXCLUDE_FILES/FOLDERS` | Inferred source root и default corpus exclusions; explicit source/locale/version/network boundaries сохранить. Direct GitHub SDK не приписывать default factory: factory возвращает WebFetcher. |

Дополнительный read-path scope: `_answer_units_part01.py:_context_score` содержит
inline derivational map `cleanup/cleaning/clearing→clear`, `indices/indexing→index`
(расширение D23); source attribution и proof нельзя освобождать от аудита как
«domain-neutral». `content_trust.py:_RISK_PATTERNS` и
`_action_packet_shared.py:_DANGEROUS_CONTENT_PATTERNS` — lexical safety guards,
не query→answer aliases; это SPLIT-кандидаты, не разрешение удалить safety.
Connector исключения (`fetchers/github.py`, `pipeline/filtering.py`) ограничивают
corpus, включая RU i18n; exact URL/path configuration следует отдельно проверить
на доступность RU источников, не объявлять blanket technical exemption.

157 frame decisions: [manifest](archives/p0-frame-symbol-decisions.json).
Это audit classification, не approved exceptions или выполненная migration.
Единый candidate/bridge follow-up: [P0_CANDIDATE_CLOSURE_RU.md](P0_CANDIDATE_CLOSURE_RU.md).
Inline follow-up расширяет D14 (`flutter_` dependency alias и ambiguous-name gating),
D30 (`scandoc`/`scan_doc` source rejection и local stop list), D26 (NL command cues
в `technical_terms`). Эти правила не освобождены от migration как «technical».

Пути в таблицах относительно корня репозитория.

| ID | Статус / действие | Место и конкретный механизм | Что затрагивает / замена в плане |
|---|---|---|---|
| D01 | M / REMOVE | `docmancer/docs/domain/project_retrieval_intent.py`: `build_project_retrieval_aliases`, `_INTENT_ROLE_POLICY`, `_specific_contract_request`, RU `mapping`, `project_retrieval_disposition` | Generated queries, source policies, context disposition. P3/P4. A/B доказывает выигрыши и потери, а не возможность простого удаления. |
| D02 | S / REMOVE | `docmancer/docs/domain/documentation_query_plan.py`: `_ORIGINAL_RETRIEVAL_INTENTS`, `_HOST_AUDITED_RETRIEVAL_INTENTS`, `_can_derive_original_from_intent`, `_host_lookup_can_derive_original`, `_audited_host_lookup_rewrites`, `host_policies`, `concept_queries` | Intent-based parent attribution, policy inheritance, подставленные пути/API; отдельный installation regex. P3/P4. |
| D03 | S / SPLIT | `docmancer/docs/domain/project_query_intent.py`: `PACKS_MCP_PHRASES`, `_DOCS_MCP_PHRASES`, `classify_project_query_intent`, purpose/concept helpers | Подстроки/regex задают architecture, troubleshooting, code, Docs/Packs lanes. Публичные tool names как схема отдельно от угадывания запроса. P4. |
| D04 | S / REMOVE | `docmancer/docs/domain/_project_answer_contract_part01.py:332–365,403–441`: `_concept_queries.semantic_aliases`, `_inventory_subject`, `_command_operation` | В запрос подставляются semantic terms, `Docs MCP`, `sync_project_docs`, `clear_index`. Удалить генерацию знания о продукте из вопроса. P3/P4/P5. |
| D05 | S / SPLIT | `docmancer/docs/domain/question_surface_normalization.py`: `_SEMANTIC_IDENTITIES`, `_RU_SEMANTIC_ALIASES`, `normalize_question_surface`; `question_component_rewrite.py:rewrite_component` | Ручные RU→EN соответствия и rewrite шаблоны. Span bookkeeping сохранить; смысловые таблицы заменить. P2/P5. |
| D06 | S / SPLIT | `docmancer/docs/application/need_query_schedule.py`: `_COMPOSITION_FOCUS`, `_focal_texts`, `schedule_need_queries` | RU/EN grammar cue и `limit=min(optional_limit,len(legacy))`: новый schedule зависит от старых aliases. Общий resource ceiling сохранить, эту зависимость убрать. P3. |
| D07 | S / SPLIT | `docmancer/docs/domain/retrieval_routing.py`: `_SOURCE_NAV_RE`, `_SOURCE_CONCEPT_RE`, `_CROSS_MODULE_RE`, `_CALL_PATH_RE`, `route_initial_stages` | Фразы и суффиксы `Service/Controller/...` включают source/repo-map/code-graph stages. Явные scope/target inputs и source-derived bindings вместо inferred authorization. P4/P6. |
| D08 | S / SPLIT | `docmancer/docs/domain/tool_selection.py`: `_STATUS_PHRASES`, `_QUESTION_PREFIXES`, `_PREPARE_TERMS`, `_DOC_TARGET_TERMS` | Угадывание tool из фразы. `_PREPARE_ACTION_BY_TOOL` — другой механизм: явный protocol mapping, не тематический словарь. P6. |
| D09 | S / SPLIT | `docmancer/docs/domain/request_intent.py`: `_ACTION_HEAD`, `_RUSSIAN_NARRATIVE_PREDICATE`; `mutation_intent.py:32–39`; `_unified_context_service_shared.py:_PATCH_TASK_TERMS`, `_IMPERATIVE_PATCH_TASK_TERMS` | Free-form text → read/change и операция. Quote/fence masking и validation explicit targets сохранить. Нельзя заменить удаление trigger безусловным разрешением mutation. P6. |
| D10 | S / REMOVE | `docmancer/mcp/search.py:141–165`: `_SYNONYMS`, `_tokens(expand=True)` | В Packs tool search `issue↔ticket`, `create→open/add/new` и другие придуманные связи. Внешний относительно Docs lane, входит в общий план P6. |

## B. Ranking, фильтрация, видимое окно

| ID | Статус / действие | Место и конкретный механизм | Что затрагивает / замена в плане |
|---|---|---|---|
| D11 | S / SPLIT | `docmancer/core/_sqlite_store_shared.py`: `_BOILERPLATE_KEYWORDS`, `_GENERIC_QUERY_TERMS`, `_QUERY_STOPWORDS`; `_sqlite_store_part03.py:_ranking_candidate` | Темы legal/task/project задают penalties/boosts; EN task verbs. Отделить corpus statistics/обычный lexical score от тематических списков. P4. |
| D12 | S / REMOVE | `docmancer/retrieval/_dispatch_shared.py:_intent_source_score`, `_snippet_intent_score`; consumer `_dispatch_part02.py` | Прибавки для `/tutorial/`, `/reference/`, `TestClient`, `HTTPException`, `Depends`, штраф для yield/advanced. Library-specific bias, не общий retrieval. P4. |
| D13 | S / SPLIT | `docmancer/docs/domain/project_doc_ranking.py`: `_EVALUATION_INTENT_RE`, `_PLANNING_INTENT_RE`, `_HISTORY_INTENT_RE`, `condition_lead_priority`, `project_question_lane`, `source_lane_allowed` | Из формулировки выводятся разрешённые source lanes; отдельные semantic boosts. Source metadata/структурные quotas отдельно от NL triggers. P4. |
| D14 | S / SPLIT | `docmancer/docs/application/_project_context_service_shared.py`: `LOW_TRUST_QUERY_TERMS`, `_question_explicitly_targets_low_trust_artifacts`, `LOW_SIGNAL_SINGLE_TOKEN_QUERIES`, `PLACEHOLDER_CONTEXT_DOC_RE`, `_DEPENDENCY_REFERENCE_CUE_RE` | Слова запроса снимают запрет low-trust artifacts; другие списки фильтруют текст/определяют dependency. Перенести право выбора scope в явный контракт, quality rules проверить отдельно. P4. |
| D15 | S / SPLIT | `docmancer/docs/application/_evidence_selection_shared.py:_LEGAL_INTENT_TERMS`, `_PATCH_FACT_RE`, `_QUALIFIER_PATTERNS`; `_evidence_selection_part01.py:_filter_candidates`; `evidence_candidates.py:_QUALIFIER_PATTERNS` | Legal word list участвует в допуске кандидатов; признаки negation/condition нельзя просто удалить вместе с ограничениями. P4/P5. |
| D16 | S / REMOVE | `docmancer/docs/domain/snippets.py:_intent_relevance_score` | Списки module/startup/testing/dependency → тематические boosts. P4. |
| D17 | S / SPLIT | `docmancer/docs/domain/quality.py:_COMMAND_RE`, `_IMPLEMENTATION_LOCATION_RE`, `_NOISE_PATTERNS` | Известный список CLI и NL запросов влияет на признание code/command evidence; code fences/syntax не требуют product names. P4/P5. |
| D18 | S / SPLIT | `docmancer/docs/domain/_project_answer_contract_shared.py:_HISTORY_RE`, `_CURRENT_RE`; `_project_answer_contract_part01.py:lifecycle_intent_for_question`; `lifecycle_policy.py:lifecycle_intent` | Языковые triggers выбирают historical/current filtering. Сами lifecycle statuses и проверки snapshots — сохраняемые контракты. P4. |
| D19 | S / SPLIT | `docmancer/docs/domain/context_hint_policy.py`: импорт `_specific_contract_request`, `_tokens`; `_project_docs_service_part03.py:306–345`; `_docs_context_projection_core.py:113–129` | Fallback зависит от словаря; особые условия для `fail_closed_workflow`/`intent-context:*`. Это потребители, не новые самостоятельные словари. P3/P4. |
| D20 | C / REVIEW | `docmancer/docs/domain/context_windows.py:_QUERY_STOP_WORDS`; `query_terms.py:_REQUEST_FRAMING_TERMS`, `_SUPPLEMENTAL_FUNCTION_WORDS`; `retrieval/query_planning.py:_STOPWORDS`; `legacy_question_coverage.py:_STOP_TOKENS` | Stopword/framing normalization может стирать смысл/связки. Проверить каждый список; «это stopwords» не автоматическое исключение из аудита. P0/P4/P5. |

## C. Смысловая квалификация и proof

| ID | Статус / действие | Место и конкретный механизм | Что затрагивает / замена в плане |
|---|---|---|---|
| D21 | S / SPLIT | `docmancer/docs/domain/admission_grammar.py:_WORDS`, `_FORMS`, `_ACTIONS`, `_STATES`, `_PATTERNS`; `admission_relations.py` использует `_WORDS` | RU/EN semantic equivalence, interpretation и qualification. Комментарий «grammar, not dictionary» не исключает ручные соответствия из scope. P5. |
| D22 | S / REMOVE | `docmancer/docs/domain/question_plan_command_rules.py:_docs_mcp_server_command`, `_command_sync` | План содержит `expected_value=docs-serve/sync_project_docs`, хотя команда не названа пользователем. Значение должно прийти из source evidence, не product rule. P5. |
| D23 | S / REMOVE | `docmancer/docs/domain/question_plan_proof.py:_semantic_terms` | Ручные RU/EN соответствия entry/permission/queued work используются в proof-пути. P5. |
| D24 | S / SPLIT | `docmancer/docs/domain/_answer_units_part02.py:_attribute_aliases`, `_inventory_anchor` | `timeout↔deadline`, `public tools↔commands/methods` и RU forms участвуют в подтверждении атрибута. Numeric/source binding сохранить, предметные synonym rules заменить. P5. |
| D25 | C / REVIEW | `docmancer/docs/domain/question_premise_proof.py:_ACTION_FORMS`; `question_plan*.py`, `question_semantic_frames.py`, `question_frame_core.py`, `project_answer_contract.py`; `governance_value_proof.py` | Другие natural-language frames и ontology/proof rules. Нужны symbol-level inventory и проверка всех imports, включая shards/bridges. P0/P5. |
| D26 | S / SPLIT | `docmancer/docs/domain/query_reference_binding.py:_CONTEXT`, `_ROLE_WORDS`, `_PREDICATES`, `_NON_ENTITY_ACTORS`; `technical_terms.py:_IRREGULAR_SINGULARS` | Языковая интерпретация source/subject и нормализация идентификаторов. Точные literal spans/catalog bindings сохранить, semantic guesses отдельно. P5. |
| D27 | S / SPLIT | `docmancer/docs/domain/answer_completeness.py:_LAYER_TERMS`, `_STORY_MARKERS`, `_RUSSIAN_REQUIREMENT_PATTERNS`, `_RUSSIAN_REQUIREMENT_ACTIONS` | Продуктоподобные истории про заявки/чат и UI слои используются для completeness. Проверить read/patch consumers, заменить source/task-derived obligations. P5/P6. |
| D28 | C / REVIEW | `docmancer/docs/domain/need_composition.py:_COUNT_WORDS`; `_answer_units_shared.py:_NUMBER_WORD_VALUES`; `_project_answer_contract_shared.py:_NUMBER_WORDS`; technical number/negation parsing | Общие числовые/языковые правила, не обязательно product dictionary. Решение по каждому правилу: technical normalization либо semantic mapping с migration. P5. |

## D. Patch/tool lanes и соседние механизмы

| ID | Статус / действие | Место и конкретный механизм | Что затрагивает / замена в плане |
|---|---|---|---|
| D29 | S / REMOVE | `docmancer/docs/application/_patch_constraints_service_shared.py:PHRASE_ALIASES`; consumers `_patch_constraints_service_part02.py:471,510` | `закрыть меню→closeMenu`, `быстрая информация→openInfo`, `scan doc→goToScanDocInit`. Реальные символы искать в текущем source tree, не придумывать из фразы. P6. |
| D30 | C / SPLIT | Те же patch shards: `ASSET_TASK_TERMS`, `GENERIC_CALL_SYMBOLS`, `KEYWORD_RE`; `patch_constraint_validation_service.py:POLICY_KEYWORDS`, `POLICY_DECISION_KEYWORDS`; `_patch_review_service_shared.py:LOW_VALUE_SYMBOLS`, `TASK_TOKEN_STOPWORDS` | Constraint extraction, target selection и review. Доказательства доступа/ownership не заменять topic match. P6. |
| D31 | C / REVIEW | `docmancer/docs/code_context.py:_LOW_SIGNAL_TERMS`, `_GENERIC_SOURCE_TERMS`; `source_map.py:_KEYWORDS`, `_QUERY_STOPWORDS` | Source navigation: отличить grammar keywords языка программирования от NL тематического routing. P0/P6. |
| D32 | C / REVIEW | `docmancer/docs/discovery_candidates.py:_KNOWN_DISCOVERY_CANDIDATES`; `dart_official_docs.py:DART_PACKAGE_OFFICIAL_DOCS`; `curated_sources.py` | Известные library/source mappings. Explicit identity→URL registry может быть допустимым data contract; topic→guessed library/answer — нет. P0/P6. |
| D33 | C / REVIEW | `docmancer/core/config.py:QueryRouter`; `docmancer/retrieval/query_planning.py:_PATH_ROOTS`; packaged YAML/JSON, templates и host instructions | Обход через конфигурационный regex router или перенесённый prompt dictionary. Полнота audit пока OPEN. P0/P7. |
| D34 | S / SPLIT | `docmancer/docs/domain/evidence_qualification.py`: `_COMPARISON_RELATION_MARKERS`, `_GENERAL_COMPARISON_RELATION_RE`, `_PROOF_INSUFFICIENCY_RELATION_RE` | Ручные EN relation формы участвуют в qualification; source freshness/identity guards и Markdown segmentation выделить отдельно. P5. |

Продолжение P0: [caller map и static manifest](P0_READ_PATH_AUDIT_RU.md).
Scan без threshold также сохраняет small inline collections и regex calls. D33 router
consumer подтверждён: `_apply_router` использует `setdefault`, не overwrite явного scope.
Config часть D33 теперь S; asset/installed-path часть остаётся C/OPEN.
Slice 2: [symbol/policy audit и unit probes](P0_SYMBOL_POLICY_AUDIT_RU.md).
D20 теперь S/SPLIT; D28 S/SPLIT с неутверждённым исключением для общих числительных;
premise/governance часть D25 S/SPLIT, остальные frame/bridge ветви C/OPEN.
Дополнительное product-specific исключение `DocAtlas`/`docmancer` в exact anchors
отнесено к D20. Статусы реализации всех этих записей по-прежнему OPEN.
Slice 3: [neighbor/bridge audit](P0_NEIGHBOR_BRIDGE_AUDIT_RU.md).
D30/D31 теперь S/SPLIT; D32 S/SPLIT с proposed technical registry exception.
D29 дополнена независимыми inline triggers в patch review (не только PHRASE_ALIASES).
D25 дополнена subject/tool injection surface rules и Android-specific requirement path.
Remaining frames, config/package consumers и approvals всё ещё OPEN.

## Что не удалять по одному признаку «это dict/list/regex»

Каждый оставляемый механизм должен получить техническое основание и тест. Примеры:

| Механизм | Основание сохранения / граница |
|---|---|
| Public tool/action enums, DTO fields, schema versions | Точный protocol contract; не вывод смысла из свободного текста. |
| Source identities, catalog metadata, lockfiles, version bindings | Данные текущего проекта/библиотеки с provenance; не hardcoded ответ о неизвестном проекте. |
| Parsing Markdown fences, paths, quoted spans, numbers/JSON syntax | Извлечение явно присутствующих bytes; не подстановка неназванной команды/темы. |
| Authorization, allowed scope, current-source checks, budget limits | Проверка явного контракта; удаление synonym list не отменяет ограничения. |
| `content_trust.py:_RISK_PATTERNS`, `_action_packet_shared.py:_DANGEROUS_CONTENT_PATTERNS` | Отдельный аудит роли: warning/telemetry/guard, а не поиск темы. Статус REVIEW, не молчаливое удаление и не blanket exemption для любых списков. |
| `snippets.py:_LANGUAGE_ALIASES`, format suffix maps | Метки синтаксиса/формата. Проверить, что не выбирают ответ или source scope по смыслу вопроса. |
| Fixtures, gold, negative examples, glossary внутри индексируемого документа | Evidence/test data. Не должны импортироваться runtime как query→answer/intent table. |

## Шаблон записи при выполнении

Для каждого D-ID вести запись:

`symbol | caller/entry point | evidence M/S/C | source hash | default/fallback reachability |
replacement | before/after case IDs | retained technical parts | test migration approval |
candidate SHA | reviewer | OPEN/REMOVED/TECHNICAL-RETAINED/BLOCKED`.

`DEFERRED` допустим для промежуточного релиза, но не закрывает **общий** dictionary-exit
milestone. До разбора всех C/REVIEW нельзя утверждать «других словарей не осталось».
