# Диагностика оставшихся 17 отказов

## Итог

**Найдены конкретные переходы потери данных и дополнительные конфликты ожиданий.
Исправлений продукта нет; integration остаётся красным.**

Исследуемый head: `264694706ff3c521abaf616f366db02a014362ea` (#211).
Remote main, #206/#208/#210/#211 и research сверены: соответствуют handoff.
Проверены все 89 hashes предыдущего EVIDENCE_INDEX: совпадают.
Работа выполнена в чистом candidate worktree; отчёт отдельно в audit worktree.

Ниже «место отказа доказано» не означает, что доказано безопасное исправление.
Особенно для пяти fact-loss тестов установлен точный отказ варианта, но общая
первопричина порядка выбора и безопасное исправление ещё не закрыты.

## 1. Pebble: 2 отказа — найдена более ранняя причина

В `docmancer/docs/application/need_query_schedule.py:35–37` `_focal_texts`
считает местоимение `them` самостоятельным объектом после `compose`.
`schedule_need_queries` расходует существующие четыре слота на:

1. `them`;
2. `What kind of interfaces does Pebble create`;
3. `how is it intended to compose them`;
4. `kind`.

Изначальный план содержал `interfaces`; этот запрос **не исполняется**.
Оба применения schedule дают одинаковый результат. Runtime подтверждает,
что `them`, `kind` и второй фрагмент вопроса возвращают пустые списки.
README найден исходным запросом и первым фрагментом, но их qualification=false
(`insufficient_visible_match`, ratios 0.25/0.4).

`docmancer/docs/domain/project_doc_ranking.py:680–686`
`rerank_project_doc_chunks` затем удаляет единственного кандидата:
нет qualified query IDs и нет checked context set. Первый вызов
`project_context_pack` возвращает 1 источник, второй — 0. Фильтры scope/trust
и бюджет здесь не являются местом потери.

Это объясняет и повторный тест с lookup, равным исходному вопросу.
Локальная точка для следующего исправления — допуск поискового focus в
`_focal_texts`, с сохранением лимита и negative controls. Исправление и
контрфактический PASS не выполнялись; достаточность одного такого изменения
для полного ответа ещё не доказана. Отключать qualification нельзя.

## 2. Budget=256: 4 отказа — конфликт двух оценок

| Кандидат | UTF-8 bytes | Публичная bytes/4 оценка | Pinned codec | Admission |
|---|---:|---:|---:|---:|
| docs/diverse.md | 1013 | 254 | 268 | 268 |
| docs/single.md | 1013 | 254 | 263 | 263 |

`model_visible_projection_helpers.py:82–86` берёт максимум двух оценок.
`_docs_context_projection_core.py:525–537` правильно отклоняет оба DTO.
JSON уже сериализуется без лишних пробелов; сокращение whitespace не поможет.
Даже диагностическая подстановка пустого snippet оставляет стоимость 264/259
(это невалидный ответ, только измерение накладных расходов, не предложение fix).
Удаление только двух null-координат даёт 258/253: нужный diverse всё равно не входит.

Безопасный representation-only fix в разрешённых границах **не установлен**.
Не менялись codec, лимит, обязательные поля или тесты. Повторён один представитель;
остальные три permutations и четыре PASS-controls при 800 — сохранённое evidence.

## 3. Пять fact-loss тестов: факты доходят до вариантов, затем не проходят бюджет

Для каждого сопоставлены exact V2 witnesses, входные chunks, подготовленные
варианты и native decision events. Это не вывод только по финальному ответу.

| Случай | Что уже выбрано | Отказ точного witness-варианта |
|---|---|---|
| request-flow, 2 теста | Application orchestration, затем README | MCP boundary: 805/805/819/824 > 800 |
| stale-health | stale-фрагмент, AGENT_DOCS_WORKFLOW, CHANGELOG | health: 999; sync: 850/974/985 > 800 |
| first-session | SKILL.md, установка в README | query command: 978/1006/1059 > 800 |
| evidence-selection | 2 фрагмента question-planning | selection proof: 976/983 > 800 |

Нужные witnesses существуют и проходят генерацию вариантов. Точка окончательного
отказа — `project_docs_context`, budget admission на строке 528. Простое увеличение
лимита не является исправлением. Предшествующий порядок выбора нужно разбирать
в `_facet_aware_candidates`/последующих preferences, сохраняя независимые направления
и guards. Общий безопасный ranking patch **не доказан и не написан**.

Вызовы core с меньшим бюджетом также есть в traces: это штатные пробные сборки
для recovery metadata. В таблице взят первый непустой core attempt с 800;
его результаты сопоставлены с финальными failing native assertions.

## 4. Supporting distractor: 1 отказ — найдено условие допуска

`test_project_query_does_not_return_non_project_docs_with_same_terms` действительно
индексирует `docs/note-*` как supporting **project** docs через catalog root.
Сначала выбирается `zz-authoritative-plan.md`, затем один из одинаковых notes.
Номер note меняется между запусками; вывод не зависит от его номера.

На втором `accepted` событии runtime показывает:
`component_scope_complete=false`, authoritative public IDs уже есть,
`new_components=set()`, `novel_independent_public_ids=set()`.
В `_docs_context_projection_core.py:560–572` проверка `authority_duplicate`
применяется только при полном component scope и здесь пропускается.
Следующая проверка использует другую меру полноты query coverage и допускает note.

Точное место допуска установлено. Утечка чужого project/module не наблюдается.
Изменять условие authority policy без проверки partial-question controls рано.

## 5. Ещё 5 отказов: различающиеся контрактные ожидания

- **Frozen V2 contract hash (1):** `build_project_answer_contract`,
  `project_answer_contract.py:356–363`, добавляет `fail_closed:legacy_coverage`
  и unresolved parts. Это выставляет `component_scope_complete=false`.
  Если только из копии hash payload исключить эти три поля, оба старых expected
  hashes точно воспроизводятся. Семантика защиты изменилась, не просто bytes:
  вернуть старый hash удалением guard недопустимо. Expectations не обновлялись.
- **Question plan (1):** `_subject_relation_groups`,
  `documentation_query_plan.py:360–378`, воспринимает `when should each tool be used`
  как условный фрагмент и добавляет `should each tool be used`.
  Это optional `canonical_intent`, не новая обязательная/public query:
  оба списка по-прежнему равны `[query-original]`. Тест сравнивает весь private plan.
- **Generic retrieval hint (1):** `NebulaLedger` теперь exact anchor,
  а не `query-hint-1`. `_qualify_candidate_lookups`,
  `_project_docs_service_part03.py:115–132`, отдельно проверяет original по body
  и помечает его `admission_only=true`, `qualification_route=cross_lane_body`.
  Наличие original во внутренних retrieval IDs само по себе не доказывает
  публичную attribution leak. Frozen ожидание и нынешняя семантика требуют ревью.
- **projection_clip (1):** источник длиной **672** символа укладывается в нынешний
  short-complete-source cap **704** (`context_windows.py:18–37`). Сохранённый ответ
  содержит весь исходный текст, стоимость 598, независимый validator возвращает `[]`.
  Тест требует исключения источника, хотя факт больше не обрезается.
- **Direct-15 (1):** ранее доказанный отдельный frozen README blob conflict.
  Переиспользовано проверенное evidence; sidecar не менялся.

Эти ожидания не переобъявляются устаревшими по решению агента. Требуется решение
по intended contracts; механическое изменение gold/expectations не выполнялось.
Отдельный adversarial status/300-token gate blocker из handoff также остаётся.

## Проверки и граница работ

- 25 разных native tests: **12 FAIL / 13 PASS** (15 neutral + 6 fact/authority + 4 contract/budget).
- Дополнительные повторения нужны для более раннего schedule/authority trace;
  не считаются новыми PASS или снижением общего числа failures.
- Ещё 5 из известных 17 FAIL разобраны с использованием прежнего evidence.
- В neutral safety tests входной pack пустой: их PASS **не является** доказательством
  работы post-retrieval safety на непустом кандидате после будущего исправления.
- Full CI и gate roster повторно не запускались; нового integration SHA нет.
- Product, tests, acceptance, workflows и main не изменены. Push/merge не выполнялись.
- Большой патч не писался: только внешний read-only observer и evidence.

Следующий небольшой самостоятельный участок — проверить исправление focus `them`
на отдельной ветке с FAIL-before/PASS-after и непустыми negative controls.
Для fact-loss безопасный объём изменения пока неизвестен; потребуется отдельный
разбор приоритетов. **Полная owning-cause/fix классификация остаётся NOT_DONE.**
