# M2: почему выявленная сложность пока не устранена

2026-10-02. Анализ по запросу пользователя, **не новый эксперимент и не runtime fix**.
Проверены текущий working tree, diff к HEAD `2ffb84fe` и уже сохранённые результаты.
Новые benchmark/test/model runs не выполнялись. Последняя locality-правка
остаётся непроверенным черновиком; приведённые результаты ей не приписываются.

## 1. Главный вывод

**Мы выявили конкурирующие relevance-решения, но вместо их замены согласовывали
отдельные маршруты и переставляли старые эвристики.** Общий iterator не стал
общим решением о пригодности контекста. Поэтому отсутствие общего улучшения
не опровергает диагноз переусложнения: требуемое архитектурное упрощение ещё
не реализовано.

Коммит `2ffb84fe6b6081f7cc75888154ec39ba14282c62` содержит только
`M2_SIMPLIFICATION_TRIAL01_RU.md` и raw rejected trial. Он фиксирует отказ от
наивного объединения typed/read разрешений, а не внедрение общего решения.
Развёрнутый исходный диагноз — `M2_HEURISTICS_RESEARCH_ANALYSIS_RU.md`,
особенно разделы 5, 8.2 и 9.1. Его ключевое требование — **один read-relevance
contract независимо от распознанной формы вопроса** — сейчас не выполнено.

## 2. Где именно расходятся диагноз и реализация

### 2.1. Отсутствие query qualification всё ещё блокирует чтение

`docmancer/docs/domain/evidence_qualification.py:310–524` сочетает source/reference
checks, lexical ratio и typed witness decision. Это не одна однородная проверка.
В `docmancer/docs/domain/project_doc_ranking.py:680–686` пустые qualified IDs
по-прежнему удаляют candidate, если его не сохранило отдельное exemption.

Следовательно, исходная схема сохраняется:

```text
смешанная qualification не разрешила candidate
  → prefit удаляет его
  → отдельный context-маршрут должен получить exemption
```

Повторная проверка identity/hash/span после изменения окна обязательна.
Но это не основание повторять разные lexical veto под видом одного guard.
Нет query qualification — не то же самое, что unsafe source, нерелевантный
текст или доказанная невозможность показать полезный partial context.

### 2.2. Общий список сохранил несовместимые правила

В текущем коде:

- Typed topical disposition допускает `retrieval_only` при двух body terms:
  `docmancer/docs/application/need_context_disposition.py:176–182`.
- Original-read требует три terms и adjacent pair:
  `docmancer/docs/application/read_context_admission.py:94–125`.
- Precedence preference зависит от распознанного relation и EN regex; последний
  черновик вызывает locality с `require_pair=False` и `sentence_pattern`:
  `docmancer/docs/application/need_context_projection.py:160–178`.
- Проверка applicability для одной precedence-формы отдельно знает
  `define different`: `need_context_disposition.py:70–76`. Это уже существующая
  зависимость от формулировки, не новое наблюдение о всех запросах.

`preferred_context_variants` объединяет precedence/list proposals, а
`iter_prefit_context_variants` добавляет original-read proposals. Это
orchestration нескольких policies, а не их замена.

Более того, ordinary original-read context не участвует в final pool на тех же
условиях: перед основной selection добавляются только preferred proposals
(`_docs_context_projection_core.py:362–377`), а checked fallback вызывается
при пустом `sources` (`:664–672`). Сохранить candidate до prefit ещё не значит
дать ему равное право конкурировать за место в непустом final packet.

### 2.3. «Консервативный locality» остаётся новым proxy

Три слова и соседняя пара — не необходимое условие полезного ответа:
установленный MkDocs witness перефразирует вопрос и не повторяет нужную пару.
Наличие двух или трёх слов также не доказывает полезность или правильность
направления relation. Известные negative controls проверяют отдельные
контрпримеры, не превращают этот proxy в универсальную semantic policy.

Есть и структурная неинвариантность прямо в коде: ordinary mode разбивает
предложения также по `\n`, а mode с `sentence_pattern` сначала соединяет
строки пробелами (`read_context_admission.py:114–115`). Обычный Markdown
перенос строки может разделить terms, хотя предложение остаётся тем же.
Это вывод из реализации, не новое измерение частоты таких отказов.

Последняя правка не добавила новый словарь синонимов и не содержит `if MkDocs`,
но закрепляет разные lexical режимы по форме запроса. Называть её общим
упрощением неправильно.

### 2.4. Diversity лечит один дефект ценой другого

В `_dispatch_part02.py:232–272` weighted retrieval order заменяется body/exact
counts и продвижением новых parents. Затем `_limit_sections_per_source`
(`:164–216`) окончательно тратит quota, включая один structural overflow.

Для MkDocs доказано вытеснение нужного child новым parent. Для HTTPX сохранённый
causal review показывает обратное: diversity помогает нужному parent попасть
в ограниченный набор (`m2_httpx_cross_stage_ablation.json`). Оба наблюдения
совместимы: **новизна parent не равна ни relevance, ни semantic redundancy**.

Удаление diversity оставляет другой несовершенный objective — число body terms.
Поэтому «убрать один harmful механизм» не означает «получить правильный отбор».
При ограниченном наборе одних passages выигрыши могут сопровождаться потерями
других; простая перестановка не решает сохранение разных полезных facts.

### 2.5. Имена вариантов преувеличивали глубину упрощения

В `m2_simplification_evaluation.py`:

- `plain_rank` сохраняет body/exact-count ordering (`:27–45`), downstream veto
  и packing; это не возврат к простому исходному weighted retrieval.
- `section_rank` группирует только уже найденные children (`:48–74`); он не
  меняет полноту retrieval candidate inventory.
- `--coarse-index` увеличивает индексные units (`:134–145`), оставляя старую
  логику выбора видимых окон и их допуска.
- `no-boosts` отключает только `source_requirement_boost` (`:151–154`).
  `source_weight_for_intent`, description/heading/path multipliers и другие
  preferences остаются в `project_doc_ranking.py:717–770`.

Это полезные ограниченные ablations. Но **ни один из них не является готовой
реализацией предложенного единого relevance/selection решения**. Их неудача
не доказывает, что упрощение невозможно или что нужны новые исключения.

## 3. Что реально говорят сохранённые результаты

Проверены rows/summary из `/tmp/opencode/m2-simplification-*-parity/`.
Corpus bytes и физический fixture root одинаковы; 80 cases, 48 within-budget
positives. Это exposed regression panel, не независимая оценка generalization.

| Вариант | Sufficient из 48 | Изменение required facts относительно baseline native |
|---|---:|---|
| Baseline native | 41 | Контроль |
| Shared native | 41 | Нет supported gains/losses |
| Shared plain | 42 | MkDocs gained, HTTPX partial fact lost |
| Shared tied diversity | 41 | HTTPX partial fact lost, новых supported facts нет |
| Shared section-first | 41 | MkDocs/Ruff gained; HTTPX-01/07, Pydantic-03, Ruff-07 lost |
| Shared coarse-index native/plain | 34 | Общая достаточность хуже |

`httpx-07` — partial case, поэтому потеря его документированного факта не
уменьшает счётчик 48 positives. **42/48 не является достаточным основанием
принять plain ranking.** Нельзя оценивать только полный ответ и игнорировать
сохранение полезных partial facts.

Полный regression последней проверенной версии:
baseline `150 failed / 5915 passed`, candidate-final `147 failed / 5935 passed`.
Три исправленных existing failures — доставка precedence context; это локальная
польза, не общий quality gain. Остальные failures не классифицированы полностью:
есть namespace limitation и missing `markdown_it`, но нельзя приписать им
все 147. Последний locality draft создан после этих runs.

Новые тесты также не эквивалентны native acceptance:

- Positive `test_shared_context_proposals.py:39–61` подменяет ranking на plain.
  Он подтверждает эту комбинацию, не production-native MkDocs delivery.
- Precedence negatives (`:129–142`) при наличии prefit inputs проверяют
  отсутствие preferred proposals, но не пустоту public payload всех routes.
- Existing `test_read_context_admission_boundary.py:76–90` проверяет именно
  public пустоту для своей группы negatives. Эти assertions не были ослаблены.

Количество runs и локальных PASS не должно заменять эти различия.

## 4. Что мы делали не так

1. **Согласование callers назвали заменой политики.** Общий wrapper уменьшает
   дублирование, но оставляет несколько оснований допуска/отказа.
2. **Добавили консервативный rescue, не определив замену relevance veto.** Затем
   корректный paraphrase потребовал ещё одного route-specific режима.
3. **Подменили общий критерий объединением старых разрешений.** Первый trial
   расширил admission до более слабого typed floor и пропустил шесть negatives.
   Это не опровержение упрощения, а ошибка семантики такого объединения.
4. **Сосредоточились на knobs до ответа о владельце решения.** Большинство
   старых veto и ranking objectives осталось, а benchmark измерял их сочетания.
5. **Смешали объём проверки и достигнутую пользу.** 960 вызовов и три зелёных
   existing tests не означают общего улучшения; native sufficient не вырос.

Главная недостающая часть была известна исходному анализу: чем именно заменить
некалиброванный read-relevance veto, не выдавая source eligibility за relevance
и не теряя subjects/conditions. Эта часть не была определена до реализации.

## 5. Исправленный порядок работы: анализ, не новый trial

1. Зафиксировать этот диагноз и отделить source hard guards, relevance
   preferences/veto, support/coverage и permissions в **активных callers**.
   Для каждого отказа указать вход, полномочие удалить candidate, downstream
   последствия и raw evidence. Остаточный legacy код сам по себе не доказывает
   его выполнение.
2. По существующим traces разобрать первый irreversible loss и компенсирующие
   rescues для MkDocs/HTTPX/Pydantic/Ruff и затронутых regression groups.
   Не считать все failures одного происхождения или автоматически obsolete.
3. Составить карту ответственности: один владелец read-relevance/selection,
   одинаковый контракт независимо от формы вопроса; source/span rechecks
   остаются на каждой изменившейся границе; support и permissions отдельны.
   Relevance не получает новых словарей, special relation modes или fallback
   разрешения только потому, что другой маршрут отказал.
4. До изменения алгоритма показать конкретный migration diff-map:
   какие старые veto исчезают, что переносится в preferences, где сохраняются
   guards и чем обоснован единый relevance критерий. Если замена критерия пока
   неизвестна, назвать это открытым архитектурным решением, а не скрыть его
   новым threshold или обещанием semantic scorer.

Выход следующего шага — **карта решений/противоречий и обоснованная схема
упрощения**, не очередной ranking arm. Не запускаем новые benchmark trials,
не меняем chunk profile, model, thresholds или runtime defaults в этом этапе.
После согласования схемы нужны implementation и non-regression, но они не
заменяют текущий анализ и не объявляются начатыми. M2 остаётся открытым.
