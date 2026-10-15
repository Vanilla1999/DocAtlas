# P1.4: два оставшихся original-only discovery FAIL на SHA107

Это аудит фактического результата и предложение следующей проверки, не product fix.
Исходные вопросы, bodies, catalog, labels, lookup policy, scorer и required gate не изменены.

## Фактическое основание

PR HEAD: `321f36577577cb90a0422cee0de0b525b9cd658e`. Проверенный root merge checkout:
`217d21017008240cf252e6b99e5c6e810a858a2a`, tree `9ea02d6b3dd7912b46000dc8174939ec0981e5d8`.
[P1.4 job 114101794605 / run 38014539453](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539453/job/114101794605):
**12/14 cases, 8/10 required discovery, 5/5 complete facts, 0 runtime errors**.
В обоих оставшихся случаях единственный failed check — `required_discovery`.
Чтение лога не запускает новый runtime; этот receipt относится только к указанному SHA.

| Case | Исходный вопрос | Единственный finite member | Полное окно | Qualifier body matches | Ratio |
|---|---|---|---|---|---|
| `alias_order_drafts` | `How are order drafts stored before upload?` | `packages/orders/README.md` | 85 chars / UTF-8 bytes | `order`, `before`, `upload` | 3/7 = 0.4286 |
| `alias_project_retry_rule` | `What is the project-wide rule for network retries?` | `ARCHITECTURE.md` | 125 chars / UTF-8 bytes | `network`, `retries` | 2/8 = 0.25 |

Точные frozen bodies, без добавленного завершающего перевода строки:

```text
OrdersDraftStore stores draft orders as JSON records keyed by order id before upload.
```

```text
ProjectRetryPolicy governs network submission retries and allows at most two retry attempts with bounded exponential backoff.
```

| Case | SHA-256 документа и найденного полного окна | Raw span |
|---|---|---|
| `alias_order_drafts` | `6f13aec3ccc8d596f1552421aa7f4e0f2f2738b6e9654eeab1621e4a07f704a1` | `[0,85]` |
| `alias_project_retry_rule` | `5a6583754d6ed2f7c294a4334f47ecacdb7087abe1116ec20d97d6373dbef32a` | `[0,125]` |

Источник questions/bodies: [frozen protocol](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/eval/agent_developer_v1/paraphrase_protocol.json), blob `43cd3b77175205d72092ab768907b6f82259a0a6`.

## Что действительно передано и найдено

- В каждой case реальный public request содержит исходный вопрос, `scope=project`, `lookup_queries=[]`.
  `prepare_project_docs`, `allow_network`, `force_refresh` в проверяемом read равны `False`.
- План содержит только `query-original`: исходные bytes, `origin=original`, `relation=direct`.
  Ни generated alias, ни host lookup, ни parent credit в наблюдаемом плане нет.
- Catalog создан только из указанного body/path: `code_files=[]`, role `other`, scope `project`,
  authority `source_of_truth`, status `active`, impact `track`, description `Pinned documentation source`.
  Подготовка выполняет реальный `prepare_docs/sync_project_docs` с `confirm=True`, текущим CAS,
  body/catalog hashes и host-selected store. Expected/indexed paths совпадают; failed/unexpected пусты.
- Оба тела найдены через lexical OR fallback. Сохранены current project identity, generation,
  catalog-entry hash, stable child, parent и полный source-reference span.
  `root_catalog_complete=True`, `root_reference_count=0`.
- В каждой case записаны две qualification records одного и того же child/window, не два разных документа.
  Обе rejected: `insufficient_visible_match`; `literal_context_admission=null`.
  `exact_terms`, `bound_subjects`, `retrieval_anchors` пусты; heading/table context не использован.
- Before/after generation, store, catalog и document hashes одинаковы; read-state differences пусты.
  Runtime error, source errors и authority errors отсутствуют. Пустой список source errors при нуле
  visible sources не является доказательством успешного positive source delivery.
- Наблюдаемый public delivery: `deliverable=False`, `required_evidence_missing`, sources 0.
  Projection/ranking/coverage в public trace — `not_reached`.
  Это не означает, что внутренний ProjectContext reranker не вызывался.

Capture/guards: [current retrieval runtime](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/eval/agent_developer_v1/current_retrieval_runtime.py)
и [finite fixture preparation](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/eval/evidence_quality_v2/runtime.py).

## Точная граница в коде

1. `build_documentation_query_plan` сохраняет original и только предоставленные host lookups.
   `build_project_retrieval_aliases` возвращает пустой tuple по действующему контракту.
2. `qualify_evidence` сначала проверяет policy/current owner/lifecycle и канонические source/reference bytes.
   Обе actual records дошли до последующего lexical comparison.
3. При пустом `exact_terms` действующий required ratio равен 0.5. Denominator включает
   `how/are` и `what/is/the/for`, но недостаток не сводится к frame words:
   `drafts` не равно `draft`, `stored` не равно `stores`; `project-wide/rule` отсутствуют во втором body.
   Изменение denominator без отдельного контракта не доказывает полноту смысла.
4. `admit_original_literal_context` сохраняет failed qualification и допускает только перепроверенный
   literal body witness: explicit quoted symbol либо полностью потреблённую identifier/count/Explain
   форму, либо current full-catalog filename reference. Для этих двух вопросов такого witness нет.
5. `rerank_project_doc_chunks` отбрасывает строку с failed trace при отсутствии проверенного literal
   admission/допустимого context candidate. Retention также требует qualified public query либо
   перепроверенный literal admission. Старый unresolved hint fallback возвращает `False`.
6. ProjectContext затем вычисляет read delivery по своему actual pack и operational operands;
   Unified/public MCP сохраняют veto до projector. Нельзя исправлять только последний boolean.

Пункты 1–5 — source-backed причинная цепочка, согласующаяся с actual qualification.
Точный ProjectContext pack count и каждый промежуточный consent/routing operand для этих двух
reads в P1.4 stdout не сохранены: текущий capture whitelist исключает `delivery_observations`.
Неизвестные поля не объявляются `False`. Для отдельного уточнения достаточно сохранить уже
собранный same-call `delivery_observations` дополнительным ключом; повторный retrieval не нужен.
Этот аудит такой diagnostic edit не вносит.

Источники: [planner](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docmancer/docs/domain/documentation_query_plan.py),
[qualifier](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docmancer/docs/domain/evidence_qualification.py),
[literal admission](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docmancer/docs/domain/literal_context_admission.py),
[project ranking](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docmancer/docs/domain/project_doc_ranking.py),
[ProjectContext](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docmancer/docs/application/_project_context_service_part01.py),
[disabled hint fallback](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docmancer/docs/domain/context_hint_policy.py).

## Почему эти два expectations остаются действующими

[Current P1.4 migration](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/eval/agent_developer_v1/paraphrase_contract_migration.json)
(blob `701808d44e9d1d96a9d02721e4909b40bfc0c2a1`) явно сохраняет для обоих:
`require_discovery=True`, `require_visible_complete_fact=False`, `lookup_queries=[]`.
Discovery теперь означает actual public source с независимо проверенными bytes/coordinates,
а не работу прежнего alias generator. Oracle не требует original coverage или answer permission
для зачёта этого source. Старое название family не отменяет это новое явное обязательство.

[ADR0003](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/docs/adr/0003-context-first-project-reads.md) отменяет automatic aliases и
answer certification из lexical совпадений, но разрешает полезные source-bound partial facts.
Позднейшее [CURRENT_WAVE decision](https://github.com/Vanilla1999/DocAtlas/blob/321f36577577cb90a0422cee0de0b525b9cd658e/v2plan/CURRENT_WAVE_DECISIONS_RU.md) явно включает
original-only paraphrase и partial admission в текущую работу. Поэтому эти FAIL нельзя удалить,
сделать optional или незаметно заменить host lookups ради зелёного gate.

## Предложение следующего narrow slice

Следующая цель — отдельный контракт выдачи полезного, но не qualified partial context.
Retrieval является эвристикой и может ошибаться; его результат не обязан доказывать полный ответ.
При этом source identity и право чтения должны проверяться строго, а качество эвристики —
измеряться независимыми positive/negative oracles. Совпадение слов не объявляется доказательством relatedness.

Перед product edit необходимо зафиксировать:

- Как request-derived literal anchors выбираются независимо от уже найденного candidate и gold.
  У существующих маршрутов это explicit lookup/symbol/source reference; у двух текущих вопросов
  такого готового carrier нет. Выбор post hoc только совпавших слов не создаёт новый authority.
- Что новый route допускает только current source-bound read context, не меняет original query/plan,
  не создаёт lookup, не выставляет qualified/coverage/answer/edit и сохраняет missing original.
- Как повторно проверяются raw source/body spans, ownership, generation, catalog, scope, lifecycle,
  request consent и final same-call public snapshot; metadata/header/link не заменяют body.
- Как кандидат сохраняется через обычный и retained ProjectContext paths и итоговый projector.
  Одного входного флага `context_eligible` или изменения `deliverable` недостаточно.
- Как related/absent/unrelated результаты измеряются без подстройки ratio/stopwords под P1.4.
  Original P1.4 остаётся неизменным контрольным набором для последующей проверки общего правила.

Минимальный independent fixture/control до выбора эвристики:

1. Отдельный finite project с новым именем/путём/полным фактом, нейтральным catalog и исходным
   prose question без hidden lookup; рядом текущий unrelated body. Ожидание — useful source text,
   исходный missing coverage и все answer/edit flags False.
2. Body swap при том же filename/catalog: полезный факт отсутствует; метаданные не спасают source.
   Отдельно удалить одну часть многосоставного факта: сохранившийся useful partial допустим,
   но полного fact credit быть не должно.
3. Common-word и literal-label контрпримеры с теми же lexical matches.
   Например, `The editor lists order, before, and upload as sample words.` и
   `The glossary prints network and retries as unrelated labels.` показывают предел одного overlap.
   Эти демонстрации не добавляются в frozen P1.4 и не определяют production thresholds.
4. Исходный запрос с отсутствующим literal/добавленным условием, а также прежние strict unrelated
   negatives сохраняют свой independent verdict. Релевантное отрицательное утверждение в документе
   не следует автоматически путать с unrelated source или доказательством желаемого ответа.
5. Реальные foreign-owner/stale-generation/hash/span/scope/consent negatives; malformed/resealed
   replay не получает source credit. Нельзя подменить эти проверки fabricated qualified trace.

Это можно разместить в одном существующем task-level control с внутренними variants и
адресными mutations после утверждения product rule; число вариантов и native reads сообщается явно.
Для P1.4 oracle отдельно полезен компактный replay: valid visible source + missing original должен
сохранять discovery PASS; removal source должен ломать discovery. Это проверка независимости
oracle от engine coverage, а не новый runtime proof и не замена required original-only case.

Здесь не предложены новый provider/model download, corpus-specific synonyms/stopwords, уменьшение
ratio или автоматический lookup successor. Готового безопасного original-only product patch
данные пока не доказывают. Два quality FAIL остаются открытыми до reviewed rule и фактического
совместного CI; соседний V2 delivery audit может локализовать более узкий дефект сохранения
уже qualified полезных windows без изменения relevance policy.

## Review и статус

Exact protocol, current migration, ADR, source boundaries и actual bounded P1.4 log прочитаны.
Независимый second opinion contracts_review_resume согласен: не obsolete alias tests;
готового literal/source-reference carrier для этих двух questions нет.
Production, fixtures, corpus, scorer, runtime calls и refs этим аудитом не меняются.
Новый PASS или готовность PR к merge не заявляются.
