# #211: причины красного CI и критическое ревью анализа

Дата: 2026-10-06. Ветка: `integration/stage3-v2-identity-pr1`.
Исследованный SHA: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.

**Статус: диагностика завершена для трёх рассмотренных случаев; исправления не
реализованы и не приняты. Это авторская критическая проверка, не независимое ревью.**

Документ закрепляет и уточняет предыдущий анализ первых двух шагов ремонта.
При расхождении с прежним выводом «нашли два узких исправления» использовать
более ограниченные выводы этого документа. Небольшой diff не доказывает узость
изменения поведения.

Машиночитаемая сводка: [PR211_RED_EVIDENCE_20261006.json](PR211_RED_EVIDENCE_20261006.json).
Это извлечение из существующих результатов, а не новый запуск. Код продукта,
tests/gold, лимиты и workflows при закреплении анализа не изменялись.

## 1. Что установлено достаточно хорошо

### A. Adversarial: повторная интерпретация обходит уже установленную границу

Сценарий `module_scope_rejects_project_policy_detail` спрашивает число retry attempts
у `ProjectRetryPolicy`. Трасса показывает:

1. Основной план: `component_scope_complete=true`, один компонент `attribute`,
   `value_kind=number`, `response_mode=count`.
2. `_docs_context_projection_core.py:89–94,248–250` включает
   `strict_single_attribute` и отклоняет README с `candidate:missing_attribute`.
3. Поздний fallback (`:665–673`) получает исходный `initially_ranked` pool.
4. `compile_need_contracts` заново трактует этот запрос как
   `relation=mechanism`, `requirement=unknown`, `interpretation=unresolved`.
5. `need_context_disposition.py:176–182` допускает context по двум совпавшим словам.
6. Финальный пакет: `ok`, 380 tokens, число попыток отсутствует.

В выдаче только `packages/orders/README.md`; запрещённые ARCHITECTURE/payments не
выданы. `answer_supported=false`, `edit_ready=false`. **Утечка scope и ложная
авторизация ответа/редактирования этим случаем не доказаны.**

Причинная проверка: отключение позднего fallback в памяти даёт ожидаемый отказ
за 244 tokens. Более ограниченный вариант — перенос уже существующего
`strict_single_attribute` на этот путь — также даёт adversarial **28/28 вместо 27/28**.

**Вывод:** доказана несогласованность двух трактовок запроса, а не необходимость
запретить любой partial context. Сохранение строгой границы — кандидат A для
первой изолированной правки, не готовое общее решение admission.

### B. Supporting notes: найдено условие, объясняющее целевой отказ

В `test_project_query_does_not_return_non_project_docs_with_same_terms` заметки
`docs/note-*` включены самим manifest fixture в project scope. Имя теста не
является доказательством попадания чужих документов.

Авторитетный документ выбран первым. Supporting note содержит
`does not define the acceptance contract`, не добавляет component witnesses,
но имеет lexical match_ratio 0.7–0.8 и дополнительное вхождение `2.3` в теле.
У авторитетного документа `2.3` находится в heading.

План не разобрал вопрос полностью: `component_scope_complete=false`.
Это выключает проверку `authority_duplicate` в
`_docs_context_projection_core.py:560–572`. Последующие проверки новизны по query
IDs допускают тематический фрагмент без нового component witness.

Удаление только зависимости `authority_duplicate` от полноты разбора в памяти
исправляет весь исходный тест. На парном наборе 85 tests:
**83 PASS / 2 FAIL → 84 PASS / 1 прежний FAIL**.

**Вывод:** найден кандидат B, объясняющий конкретный отказ. Общая безопасность
расширения этого запрета на нераспознанные вопросы пока не доказана.

### C. Hint: изменилось внутреннее представление, но нужен аудит публичного контракта

`test_query_project_docs_attributes_generic_retrieval_hints_without_covering_original`
требует `query-hint-1` и отсутствия original в `retrieval_query_ids`.

В текущей трассе:

- `NebulaLedger` найден через `query-anchor-1`;
- original проверен независимо на body, `qualification_route=cross_lane_body`;
- original имеет `admission_only=true`, lexical_score=0;
- `qualified_query_ids` содержит anchor и original;
- `attributable_query_ids` содержит **только anchor**.

`context_selection.py:267–276` исключает admission-only из публичной attribution.
`derived_parent_trace` не наследует original coverage из relation=exact_anchor.
Более новый тест `test_discovery_independent_qualification.py:29–37` требует
независимой проверки original query и проходит.

История: тест — `d30aeec1`, появление anchors — `2facdba3`, независимая original
qualification — `340759b4`. Это объясняет устаревание конкретного имени ID.

**Вывод:** production не следует подгонять под строку `query-hint-1`. Но история
коммитов и новый тест сами по себе не являются одобрением смены контракта.
Проверка `attributable_query_ids` на промежуточных metadata ещё не доказывает
сохранение границы в final public packet, после crop/requalification/merge.

## 2. Где предыдущий анализ был слишком уверенным

| Прежний вывод | Критика и исправленная формулировка |
|---|---|
| «Два узких исправления найдены» | Найдены два небольших контрфактических изменения с разной доказательной силой. A сохраняет существующее ограничение; B расширяет политику отбора на unknown-случаи. |
| «Тест hint устарел» | Устарело имя discovery ID; вопрос о сохранении публичной атрибуции требует отдельного end-to-end доказательства. Нельзя просто заменить обе строки assertions на фактические значения. |
| «0 новых отказов — нет регрессий» | Нет новых failure IDs относительно указанного CI в измеренном core roster. Это не проверка всех контрактов и не доказательство неизменности поведения проходящих tests. |
| «Нет witness — supporting-фрагмент лишний» | При неполном parser отсутствие распознанного witness не доказывает отсутствия полезного факта. Это главный риск кандидата B. |
| «Эвристики объясняют красное» | Конкретные связи установлены для описанных маршрутов. Наличие regex/словарей не доказывает причину всех 17 отказов или всех quality failures. |
| «380>300 — ошибка переданного лимита» | В fixture 300 остаётся evaluator ceiling, но `packet_tokens` не передаётся handler. Это FAIL протокола оценки, не доказанный сбой caller-budget transport. |

### Недостатки проверки, которые нельзя замалчивать

1. Полный неизменённый baseline core в том же локальном окружении в этом анализе
   не запускался. Сравнивались локальный Python 3.13 candidate и сохранённый CI
   baseline; машинное сравнение использовало job Python 3.11. Парный локальный
   baseline есть для 85 tests и adversarial. Прогон с отключённым fallback —
   **тоже вмешательство**, его нельзя подписывать baseline.
2. Полный core оставляет 622 deselected. Это не весь CI. Advanced/security,
   legacy lineage floor, mutation, installed-package и оставшаяся Python matrix
   на кандидатах не подтверждены.
3. Полный core кандидата проверял A+B вместе. Это не полная факторная проверка
   A отдельно, B отдельно и их взаимодействия.
4. Supporting-positive probes выбирали supporting source **первым**. Они не
   проверяют риск его удаления **после** authoritative source. Их успех не
   закрывает риск кандидата B.
5. Strict-attribute veto может снизить recall, если source содержит число, но
   основной witness detector его не распознал. Нужен положительный контроль
   реального числа и фактической доставки, а не только ожидаемого отказа.
6. Диагностическая Python-подмена не равна реальному исходному patch. После
   реализации нужны проверки на конкретном новом SHA.

## 3. Эвристики: что действительно обнаружено

| Место | Правило | Что оно не доказывает |
|---|---|---|
| `need_context_disposition.py:176–182` | >=2 совпавших body terms | Связь терминов в одной ситуации, наличие ответа |
| `evidence_qualification.py:460–466` | Lexical overlap 0.4/0.5 | Полноту запрошенных фактов |
| `project_retrieval_intent.py:49–88,160–178` | Intent → preferred/forbidden roles и forbidden terms | Универсальность тематического маршрута |
| `documentation_query_plan.py:552–557` | Специальная RU-форма вопроса об установке | Эквивалентность произвольных перефразировок |
| `admission_grammar.py:39–79,151–187` | Ограниченные RU/EN словари и regex frames | Полное понимание естественного языка |
| `context_candidate_ranking.py:303–354` | Частные формы и tuple приоритетов | Семантическое превосходство выбранного пакета |

В придуманной диагностической пробе `ProjectRetryPolicy` из одного абзаца и
`retry` про другого worker из соседнего дали `retrieval_only` и native `ok`.
Это демонстрирует слабость topical admission, но не ложный `answer_supported`:
answer/edit flags оставались false. Пробы не являются независимым holdout,
оценкой ответов LLM или измерением частоты такого дефекта на реальных запросах.

Regex, dictionaries и thresholds не следует удалять по самому факту существования.
Структурный parser, exact identity checks и retrieval ranking выполняют разные
обязанности. Проблема здесь — противоречащие друг другу интерпретации запроса и
использование lexical novelty там, где ожидают фактическую полезность.

**Не добавлять новые словари, blacklist, языковые исключения, regex или weights
ради этих примеров. Не понижать acceptance и не повышать бюджеты.**

Основная часть исследованных правил уже была в main `d2ed5c4c`. Strict guard
появился в `ce0fc279`, fallback — в `d4c6bb7a`. Их история не доказывает точный
первый failing SHA без исторического запуска и не оправдывает baseline FAIL.
`reviews/demand-evidence-delivery/product-transfer.md:19–21` сообщает 242 targeted
PASS и отсутствие full gate на transfer; это не общая продуктовая приёмка.

## 4. Зафиксированные измерения

| Измерение | Результат | Граница вывода |
|---|---|---|
| Baseline CI core | 5282 PASS, 17 FAIL, 10 skipped | SHA `37bfd066` |
| Baseline adversarial | 27/28; три сообщения о нарушениях | Один failing case; два сообщения относятся к token ceilings |
| Strict-attribute counterfactual | Adversarial 28/28 | Проверка A в памяти |
| Отключение всего late fallback | Core 5282 PASS / 17 FAIL; те же failure IDs | Диагностика, не предлагаемое исправление |
| Authority, парный набор 85 | 83/2 → 84/1 | Целевой notes case исправлен |
| A+B, исправленный runtime-стенд V2 | Core 5283 PASS / 16 FAIL; adversarial 28/28 | 0 новых core failure IDs, снят только notes case |

Hint assertion остаётся красным. Остальные 16 core failures и legacy floor
`10 < 12` не объявлены исправленными. Сравнение failure IDs находится в JSON рядом.

### Ошибка диагностического стенда сохранена отдельно

Первый A+B replay: **5280 PASS / 19 FAIL**, три дополнительных language-hook failures.
Причина проверена контролем: копирование **неизменённой** функции в отдельный
globals dict воспроизводит те же три FAIL. Native baseline — 3 PASS; corrected
candidate с исходным `core.__dict__` — 3 PASS. Исправлена только привязка runtime
стенда, затем повторён весь core. Старый результат не переписан и не засчитан.

Это делает исправление стенда обоснованным, но также показывает, почему окончательная
приёмка должна выполняться на настоящем diff, а не только monkeypatch/exec replay.

## 5. Исправленный порядок работы и критерии допуска

### A — первый кандидат для отдельной реализации

- Сохранить уже вычисленную strict-attribute границу на late fallback; не
  создавать третий parser и не отключать весь partial context.
- Проверить baseline FAIL → candidate PASS в исходном adversarial case.
- Положительные контроли: источник с нужным числом; частичный контекст вне этой
  strict-границы; тот же факт при изменении структуры исходного фрагмента.
- Отрицательные контроли: число у другого subject, неверный scope/identity,
  stale/unsafe source. Проверять финальные цитаты и flags, а не один status.
- Полный core и обязательные проверки на фактическом patch/SHA.

### B — HOLD до проверки полезного supporting-контекста

- Не переносить удаление `component_scope_complete` в продукт только по одному
  выигранному тесту и отсутствию новых core failure IDs.
- Нужна парная проверка: authoritative source выбран первым, supporting source
  добавляет реально нужный факт, parser не полностью распознал вопрос.
- Сопоставить с таким же порядком источников для бесполезного distractor.
- Проверить сохранение независимого lookup и дополнения того же источника.
- Если полезный факт теряется, отклонить B. Не спасать его новым blacklist,
  исключением для конкретной библиотеки или новым весом ranking.

### C — аудит тестового контракта, без автоматического обновления ожиданий

- Зафиксировать distinction: discovery, internal qualification, public attribution.
- Проверить отсутствие ложного original coverage в final packet после
  requalification/crop/merge; поддельный trace не должен давать coverage.
- Сохранить negative controls на unrelated body и foreign identity.
- Только после доказательства и отдельного согласования заменить устаревшие
  assertions. Нельзя удалять сценарий, добавлять skip/xfail или просто принимать
  текущие IDs как gold.

После A не ждать, что прочее красное исчезнет автоматически. Для оставшихся
отказов — отдельные причинные трассы, без глобальной переделки ranking/parser.
Работа остаётся в #211; merge в main требует обязательный CI, независимое review
и явное разрешение владельца. Этот документ такого разрешения не даёт.

## 6. Где находятся доказательства

- [Core CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37347840210).
- [Основной CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37347840400).
- [Adversarial CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37347840282).
- В репозитории закреплена самодостаточная сводка результатов, выбранных trace
  полей, ограничений и SHA-256 оригинальных файлов: JSON рядом с этим документом.
- Полные локальные traces, JUnit и диагностические scripts: первоначальная папка
  `/tmp/opencode/pr211-red-analysis`. В исходном анализе использованы
  `deep-scope-trace.json`, `deep-hint-trace.json`, `deep-notes-trace.json`,
  `strict_attribute_probe.py`, `authority_probe.py`, `authority_probe_v2.py`.
  Полные локальные артефакты здесь **не архивированы**; hashes не заменяют их bytes
  и не гарантируют сохранность временной папки. Для независимого воспроизведения
  перед реализацией потребуется сохранить полный пакет либо выполнить новый run.
