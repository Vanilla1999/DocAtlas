# P0: application partition — поэлементные решения и открытые границы

Дата: 2026-10-06. Область: только 607 units из 92 application source files.

**Покрытие входа полное; семантическое закрытие P0 не достигнуто.** Для 358 units
есть поэлементное source-grounded решение; 249 честно оставлены `OPEN`.
Наличие строки, AST owner или SHA pin не означает завершённый consumer audit.

## Артефакт и проверка полноты

Решения: `archives/p0-agent-application-decisions.json`.
Формат: `{partition: "application", rows: [...]}`; ровно одна строка на input unit,
в исходном порядке, без объединения owners и без blanket решения по filename.
Каждая строка содержит `path`, `owner`, `source_sha256`, `decision`, `reason`,
`consumers`, `preserve`, `reachability`, `limitations`.

| Проверка | Результат |
|---|---:|
| Input units / output rows / уникальные `(path, owner)` | 607 / 607 / 607 |
| Source files с совпавшим SHA-256 | 92 / 92 |
| Owners, сопоставленные с реальным AST | 607 / 607 |
| Input nodes / unresolved input nodes | 2793 / 2486 |
| REMOVE | 42 |
| SPLIT | 81 |
| TECHNICAL-RETAIN-CANDIDATE | 235 |
| OPEN | 249 |
| Reachability: default / fallback | 12 / 1 |
| Reachability: static-edge-only / unresolved | 517 / 77 |

SHA-256 входного gzip:
`0a9fb602dac9182eb7993966db4fbd91469eb14be9ca417d4c835dfb6ba8c53a`.
SHA-256 JSON решений:
`7207e2e5ddf64b32c61226de8caaef2481c11658f1d1d0ebb118a801549a8680`.

Все pins повторно проверены после формирования JSON. Дополнительно проверено
точное равенство упорядоченных `(path, owner, source_sha256)` входа и выхода.
Тесты не запускались: это source inventory, не regression acceptance.

## Метод и предел доказательства

Прочитаны D01–D38 в `DICTIONARY_INVENTORY_RU.md`, реальные определения,
short-owner bodies, selected larger mechanisms и явные call sites. Для всей
partition выполнено AST сопоставление owners, expressions, вызовов и references;
production modules не импортировались и не исполнялись.

В `limitations` каждой строки находятся:

- точный диапазон owner, SHA-256 текста owner;
- все unresolved expressions из входа, а не только первый пример;
- статические dependency call references, включая честно неразрешённые bindings;
- source excerpt до 2500 символов и явный флаг его усечения;
- количество consumer references и количество невыведенных references;
- различение `individually source-reviewed` и `OPEN: source/AST boundary mapping only`.

Consumer references — production syntax sites с path/line/owner. Name/import и
module-attribute references отделены от `self/cls spelling-edge` и wildcard
facade exports. Последние **не являются доказательством разрешённого MRO или
фактического исполнения**. Возможные local shadowing и runtime bridge dispatch
не скрыты. В строке выводится до 20 references; полный transitive caller closure
этим pass не заявлен. После ручного дополнения consumer sites у
`requirement_value_visible` остаются 76 пустых consumer arrays; они не означают
dead code. Reachability этого helper остаётся `unresolved`: вызовы в source
найдены, но runtime import/facade binding не проверен.

`TECHNICAL-RETAIN-CANDIDATE` — не approval и не исключение из дальнейшего P0.
Технический serializer не освобождает вызываемый им semantic parser. `REMOVE`
означает направление миграции ручного inference, а не немедленное удаление guard.
`SPLIT` привязан к двум конкретным механизмам внутри owner, не к смешанному файлу.

## Подтверждённые механизмы

### Второй проход: промежуточный результат, не завершение всей OPEN очереди

Исходные 263 OPEN просмотрены в source/AST сводках enclosing owners: calls,
branches, regex и collections. Такая сводка **не заменяет полный source review**
крупного owner и его dependencies. Полностью разрешены ещё 14 локальных owners:
13 `TECHNICAL-RETAIN-CANDIDATE`, один `REMOVE`; новых `SPLIT` нет.
Проверка всех 263 до окончательного решения **не завершена**; 249 остаются OPEN,
а не автоматически получают техническое исключение по DTO-имени.

Полные локальные тела, основание и сохраняемые ограничения перечислены в
`reason` с префиксом `Second pass:` и обновлённом `limitations.mechanism_review`:

- `_normalized_fact_text`: форматная нормализация, не semantic certification.
- `_policy_polarity`: `REMOVE` fixed English normative inference; сохранить
  различение negation/positive и неизвестность, не превращать удаление в pass.
- `_EMOJI_RE`: Unicode display cleanup, не semantic query vocabulary.
- `_read_python_dependencies`: literal exact-version grammar и TOML schema;
  неполное dependency coverage не объявлено полным.
- `compact_section_labels`: authenticated grouping, full representative и
  suffix collision guards; canonical bytes и verifier authority не заменяются.
- `merge_query_matches`: supplied trace merge, не producer qualification.
- `validate_context_selection_payload`: explicit DTO consistency, visible
  evidence и canonical assignment IDs, не доказательство assignment semantics.
- `visible_assignments`: source/span/hash identity; equal hashes не дают
  взаимозаменяемость sources или requirements.
- `requirement_value_visible`: escaped term boundaries и bounded identifier
  spelling. Добавлены реальные source calls в selection part02:188 и
  part03:606; прежний пустой consumer array был неполным static mapping.
- `compact_recovery_action_for_budget`: schema compaction с сохранением
  protected confirmation_reason и явным oversized результатом.
- `structural_spans`: list continuation и LF/CRLF boundaries, не proof.
- `unseen_adjacent_range`: bounded source interval вне visible lines.
- `verified_missing_ranges`: verified assignment offsets → source line ranges;
  `_assignment_span` и `visible_assignments` прочитаны, missing IDs supplied.
- `SourceReferenceContext._document`: selected SQLite generation, parameterized
  queries и content digest; store/parser/authorization отдельно.

Для локальных technical helpers достаточно named direct source consumer;
полный универсальный runtime graph не является требованием классификации.
При этом MRO/facade и semantic producer limitations сохранены явно.
Повторно проверены 607 ordered input tuples, 92 source SHA pins и 607 AST spans.
Input gzip и существующий trust-file hash не изменились. Production/common,
tests/gold/status файлы этим проходом не редактировались; тесты не запускались.

Пути ниже относительно `docmancer/docs/application/`.

### D06: schedule не независим от legacy envelope

`need_query_schedule.py:_COMPOSITION_FOCUS` распознаёт RU/EN composition verbs;
`_focal_texts` смешивает этот trigger с исходными focus/category spans, quotes,
RU→ASCII focal preference и full-clause fallback. `schedule_need_queries:96–98`
вычисляет `limit=min(optional_limit,len(legacy))`, затем focal groups.
Это `SPLIT`: нельзя удалять общий потолок 0..12, exact span equality, protected
quotes, explicit host/path priority и отсутствие per-need budget multiplication.

Default application call sites: `_project_context_service_part01.py:72–74` и
`_project_docs_service_part03.py:182–184` вызывают `scheduled_plan`, который
вызывает schedule и focal extraction. `default` здесь означает source-visible
обычный application path, не runtime coverage всех conditional ветвей.

### D09/D14: lexical next-action и trust gates

`_unified_context_service_part01.py:654–665:_patch_constraints_next_action`
использует `_PATCH_TASK_TERMS`/imperative prefixes/verbs, но отдельно проверяет
project_path и library mode. Owner — `SPLIT`; word assignments — `REMOVE`.
Следующее действие не является разрешением выполнить mutation.

`_project_context_service_shared.py:384–457:_query_relevance_gate` смешивает
weighted substring relevance с structured diagnostics. Вызов расположен в
`_project_context_service_part01.py:686`. `_make_context_trust_decision:460–505`
вызывается там же на `761` и смешивает low-signal denylist/score/broad intent
с независимыми typed-proof и relevance checks. Оба owner — `SPLIT`.
Локальный relevance guard нельзя превращать в безусловный pass.

`LOW_TRUST_QUERY_TERMS` позволяет wording запроса влиять на исключение risky
artifacts; это semantic inference. `LOW_TRUST_PROJECT_RISK_FLAGS` — другой
механизм: typed taxonomy enum, только technical retain candidate.

### D15/D30/D37: admission и requirement construction

`_evidence_selection_part01.py:339–341,373–376:_eligible_candidates` вычисляет
legal intent пересечением query tokens с `_LEGAL_INTENT_TERMS`. Это `SPLIT`
owner: lexical legal admission отделено от forbidden/stale/risk/project/module/
exact-version/identifier guards. Сам wordlist — `REMOVE`.

`evidence_candidates.py:projected_text` смешивает `_PATCH_FACT_RE` fact lines
с literal snippet/path/symbol bytes; `normalize_candidates` добавляет строгие
stable-child/parent/span/hash и host-policy identity checks, но вызывает этот
projection и `extract_answer_units`. Оба owner — `SPLIT`, не exemption за DTO.

`evidence_requirements.py:build_requirements` содержит inline facet/code/Cyrillic
ветви и `FROZEN_LEGACY_QUESTIONS` arbitration (`454–475`), наряду с explicit
public requirements и fail-closed unresolved handling. Решение `SPLIT` сохраняет
независимый explicit public contract; frozen registry не предлагается переносить
в новый registry. `_project_answer_facets` — `REMOVE` ручных NL facets.

### Ranking остаётся в semantic scope

`context_candidate_ranking.py` не освобождён комментарием «never proof»:
`_context_rank` содержит action word/regex и question/source lane priors;
`candidate_key` — comparison markers, request/condition/action preferences;
`_relation_request_priority` — reporting/proof/recovery/permission/condition
phrases. Эти owners — `SPLIT` с сохранением qualification, exact assignments,
original alternatives, negation и direct/derived/public/host distinctions.
Приоритет или selection stopping не должны становиться answer certification.

### D29/D30: patch extraction и validation

`_patch_constraints_service_part02.py:_term_variants` — конкретный `SPLIT`:
identifier case/underscore transforms плюс `PHRASE_ALIASES` expansion.
`_owner_from_line`/`_delegate_target` в part03 смешивают relation/role vocabulary
с source identifier captures. `_sort_constraints.relevance` содержит layer и
dependency word boosts рядом с changed-file/source-text overlap.

`patch_constraint_validation_service.py:_line_has_decision_shape` и
`_line_adds_policy_decision` смешивают source operators/branch syntax с ручными
policy/status/role/access словами. `_is_safe_ui_wiring_line` добавляет конкретные
API exemptions (`closeMenu`, navigation APIs, Notifier/Controller shapes).
Решения `SPLIT` не разрешают убрать decision-shape rejection и выдать UI wiring
blanket policy permission. `_lockfile_change_allowed` — `REMOVE` lexical
permission inference, сохраняя unresolved/manual-review результат.

### Fallback и facade edges

`_unified_context_service_shared.py:_snippet_first_fallback_question` — `REMOVE`
semantic query append «example code snippet», reachability `fallback`.
Реальный consumer: `_unified_context_service_part02.py:179–232`;
guards: response_style=`snippet-first`, library results и отсутствие уже
выбранного primary snippet. Original query, exact version и network boundaries
не должны исчезнуть вместе с append heuristic.

`docs_context_projection.py:78–82` — technical retain candidate регистрации
facade hooks, не словарь запросов. Class shard bridge calls в шести service
facades также отдельные technical candidates. Наличие bridge не доказывает,
что каждый exported helper исполняется в default request.

### Сохраняемые технические кандидаты

Поэлементно выделены JSON Schema/output field allowlists, existing support
envelope serialization, citation IDs, identity/snapshot/content hashes,
scope/path containment, exact version enums, source span bounds, job
lease/cancellation/terminal-state rules, diagnostic redaction, token/resource
ceilings и pinned offline tokenizer grammar. Это разные конкретные механизмы,
не blanket exemption для application или regex files.

## OPEN: очередь незакрытых проверок

249 строк остаются `OPEN`; полный список и индивидуальные expressions/dependencies
есть в JSON. Наибольшие группы:

| Файл | OPEN owners |
|---|---:|
| `_patch_constraints_service_part02.py` | 15 |
| `_patch_constraints_service_part01.py` | 10 |
| `_patch_constraints_service_shared.py` | 9 |
| `_patch_review_service_part01.py` / `part02.py` | 9 / 9 |
| `_project_docs_service_part01.py` | 9 |
| `_unified_context_service_part02.py` | 9 |
| `_evidence_selection_part02.py` | 8 |
| `docs_target_service.py` / `model_visible_projection.py` | 8 / 8 |

Дальнейший audit обязан прочитать полные large owners и transitive consumers,
особенно `_effective_authority`, packet fidelity/build/validate, selection
orchestration, exact-document/source continuation, source discovery/version
fallback и model-visible projection. Также не утверждены blanket exemptions
для generated/artifact/corpus path exclusions, emoji suppression,
`_ASCII_TOPIC` language preference и destructive-task safety regex.

Для `OPEN` нельзя подменять отсутствие доказательства ни `REMOVE`, ни retain
approval, ни утверждением default reachability. Gate остаётся открытым.

## Границы изменений

Созданы только этот отчёт и `archives/p0-agent-application-decisions.json`.
Production, tests, gold, common runners и status files не изменялись.
Replacement/packaging implementation не выполнялась.
Применимых `AGENTS.md` в repo и проверенных ancestor directories не найдено.
Существующий local trust diff не тронут: SHA-256
`docmancer/docs/domain/project_retrieval_intent.py` остался
`ddbaa54285e315c8267c1a1c3db3827b53b68e365991a4119805801c9751505e`.
