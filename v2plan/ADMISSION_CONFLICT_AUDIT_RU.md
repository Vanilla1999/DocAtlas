# Что отбрасывается и где конкурируют решения

Read-only аудит 2026-10-03. Production, retrieval, compiler, budgets и guards
не изменены. Нового predicate нет.

## Карта обязанностей по текущему коду

| Механизм | Что делает | Где возникает конкуренция |
|---|---|---|
| `read_context_admission.py:80–105` | Вызывает qualification, разрешает только два reason strings, затем applicability и locality | Proof reason становится read veto даже до самостоятельной relevance проверки |
| `read_context_admission.py:108–139` | Три query terms в substantive sentence + adjacent query pair; без heading/echo | Lexical форма вопроса используется как необходимое условие полезности |
| `need_context_disposition.py:130–182` | Qualification по отдельному need, applicability; supported только с witness, иначе retrieval_only при двух body terms | Другой query scope и более слабая locality для read context |
| `need_context_projection.py:160–188` | Precedence/list preferences; precedence сохраняет три terms, но заменяет pair relation pattern | Альтернативное основание предложения и порядок выбора, не proof |
| `read_context_admission.py:210–231` | Prefit сохраняет preferred/read variants; final fallback сначала typed, потом original-read | Доступность контекста зависит от этапа и выбранного пути |

Важно: наличие нескольких вызовов guards не само по себе ошибка. После clipping
source/request/span и relevance должны проверяться заново на actual visible bytes.
Убирать нужно конкурирующие **политики**, не повторную проверку изменённого окна.
Двухсловный путь тоже не является разрешением любых двух слов: перед ним есть
qualification reason filter, identity, source и applicability проверки.

## Что уже измерено: независимые слои

Источник: `artifacts/admission-layers-02/layers.json`; сохранённый owner inventory,
не новый native-inventory replay. 269 proposals; 52 имеют полный literal witness
по frozen annotations. Labels используются только после admission.

Совместные отказы независимых diagnostic слоёв на этих 52 окнах:

| Слои, не прошедшие diagnostic | Окон |
|---|---:|
| Только topic locality | 23 |
| Только condition | 5 |
| Topic + condition | 4 |
| Condition + subject | 2 |
| Topic + literal | 2 |
| Ни один из этих четырёх | 16 |

Это не causal ablation, не число потерянных claims и не разрешение ослабить guards.
В частности, source eligibility/reference checks не включены в четыре столбца.
Всего topic false: 29/52; native read allowed: 16/52.

Примеры topic-only diagnostic потерь: `starlette-06` background tasks,
`pydantic-06` aliases, `httpx-01/02/03` timeouts, `ruff-02` preview,
`uv-01/02/05` compatibility. Для `httpx-06` первый native refusal —
`verified_local_demand`, хотя отдельный topic diagnostic также false: один
first-reason не раскрывает все препятствия.

Обратное расхождение: семь witness окон проходят topic, но native read отказывает:
`fastapi-01/07` — missing_bound_subject; `starlette-03`, `pydantic-05`,
`ruff-04/05`, `uv-03` — condition_support_unavailable. Topic pass не заменяет
identity/applicability. Frozen witness наличие не доказывает корректность
request-specific interpretation этих guards.

Native/research adapter disagree по allow/reject на одном из 269 proposals
(native разрешает, adapter нет). Это расхождение adapters, **не** измеренная
матрица original-read против typed двухсловного пути. Последняя ещё не построена.

## Что доказал минимальный вариант упрощения

Отдельный `UNIFIED_READ_RESULT_RU.md`: 429 distinct captured native candidates,
80 cases, identical inventory/compiler/budget/selector. Убрана зависимость
research read decision от proof reason whitelist, сохранены locality и guards.

Результат: 80/80 одинаковых payloads, 18 packets, 11 supported в обоих arms.
Следовательно, coupling можно исключить в **измеренной isolated boundary** без
наблюдаемой потери. Это не доказательство безопасной production миграции: полный
исторический pipeline имел 49 supported и другие пути; их замена не проверена.

## Как действительно упростить

Целевая структура — не новый compiler или fallback:

1. Source/request eligibility: одна общая политика, повторная проверка окна.
2. Read relevance: одно решение о полезности, без proof reason whitelist.
3. Claim support: отдельное доказательство facts/completeness.
4. Selection: порядок и budget; preference не должна давать скрытое read permission.

**Пока нельзя выбрать ни правило двух слов, ни правило трёх слов как общее.**
Первое слабее, второе теряет annotations; снятие topic veto ранее дало packets
во всех восьми unanswerable cases одного шаблона. Новое правило не сформулировано.

Следующая проверка до удаления production веток: на одних exact visible windows
сопоставить original-read, каждый typed need disposition и preference membership.
Сохранять отдельно need scope, qualification reason, identity/applicability,
locality и prefit/final membership. В разногласиях отличать:

- useful partial vs whole-request sufficiency;
- weak relevance admission vs нужный ordering;
- wrong subject/state vs ошибочную интерпретацию question;
- actual changed window vs разные policies на одинаковом окне.

Не объединять разрешения через OR: это новый fallback. Не объединять все veto
через AND: это сохранит самые строгие recall потери. Если общего read контракта
не получается, остановить replacement, а не добавлять exceptions.

## Роль исследований

Callan мотивирует учитывать контекст passage, BEIR — простой retrieval baseline
и междоменную проверку, Sufficient Context — различать useful/sufficient/answer.
Они не доказывают наши lexical thresholds и не дают готовый model-free predicate.
В этом аудите новые научные источники не проверялись; используем ранее записанный
обзор `ADMISSION_DIRECTION_REVIEW_RU.md`, не объявляем новое literature validation.

## Вывод

Переусложнение подтверждается различными владельцами read permission и
асимметрией prefit/final, а не количеством строк. Самая сильная наблюдаемая
relevance потеря — locality. Удаление proof/read coupling само по себе её не
исправляет. Безопасный результат сейчас — карта обязанностей и точные группы
расхождений; production удаление gates пока не обосновано.
