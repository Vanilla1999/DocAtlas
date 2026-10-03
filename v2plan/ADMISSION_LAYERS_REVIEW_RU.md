# Разделение admission: subject / literal / condition / topic

2026-10-03. Research diagnostics, **не новый admission и не permission**.

## Главное уточнение к прежнему исследованию

Research adapter вызывает `_visible_term_present(lowercase_term, original_body)`.
Этот private helper сам не lowercases текст; native qualification делает это
на своём пути. Следовательно, часть записанных `missing_exact_or_subject`
отказов — **ошибка case handling adapter**, а не отсутствие requested имени.

На 52 owner proposals с complete literal witness 19 получали этот first refusal;
на **15 из 19** нормализованная независимая проверка не обнаружила missing literal
или unresolved subject. Например, `Typer.Exit`, `HTTPX`, `AliasPath` присутствуют,
но lowercase term не совпадал с исходным case. Прежние списки missing names в
`GROUNDED_LOSS_ATTRIBUTION_RU.md` нельзя использовать как корректный диагноз.

Важно: **все эти 15 proposals также отвергаются native read**, но по topic или
condition gate. Нет доказательства, что исправление adapter само восстановит
потерянные baseline claims. Исторические probe/results не переписаны: новый
диагностический script использует нормализацию существующего native qualification.
Это не новая identifier equivalence или разрешение arbitrary case alias.

## Независимые измерения, а не только первый отказ

Script `admission_layer_probe.py` читает archived hits/generation read-only,
строит прежний owner inventory и измеряет каждый layer даже после более раннего
veto. Annotation только помечает witness-bearing proposals после измерения.
Не меняет search query, budget, source guards или final packet.

| Layer observation | Все 269 proposals | 52 complete-witness proposals |
|---|---:|---:|
| Subject не найден в body/verified owner | 11 | 2 |
| Required literal отсутствует после native-style normalization | 38 | 2 |
| Condition не распознана как applicable | 42 | 11 |
| Topic locality не проходит | 237 | 29 |
| Native read allowed | 21 | 16 |

Столбцы пересекаются, не суммировать как взаимоисключающие failures. Условия
`unresolved_or_inapplicable` не различают parser limitation и действительный
wrong condition. Topic вычисляется отдельно из request/body terms, не из cached
qualification approval. 52 windows — не 52 cases и не 52 delivered claims.
Zero owner-derived subject в этом corpus не означает, что механизм невозможен:
отдельный synthetic test проверяет successful owner binding.

## 1. Subject: принадлежность, не обязательное повторение имени

Existing `prepare_reference_probe` уже связывает semantic subject с actual body
или **проверенным непосредственным structural owner header**. Каталог, URL,
project identity или название файла не являются namespace certificate.

Нужные решения:

- Subject присутствует в body → учитывать exact current occurrence.
- Subject отсутствует в body, но подтверждён actual owner → source-bound subject,
  не missing literal. Owner должен быть verified того же window/generation.
- Subject только в соседнем разделе, ссылке, имени проекта → unresolved/reject.
- Library subject отсутствует и в body, и в owner (`fastapi-01`/`07`) → не
  разрешать по каталогу. Возможность другого trusted namespace binding пока
  не установлена; это отдельный контракт, не алиас на source path.

Mutation test: heading `QueueTasks` разрешает subject binding для literal exact
window без повторения имени. Heading `OtherTasks` не разрешает. Подмена serialized
owner на `QueueTasks` отклоняется source verification.

## 2. Literal: нельзя заменить ownership или topic score

Symbol identity / explicitly requested literal — отдельный слой. Если вопрос
требует literal API, owner subject не доказывает наличие этого API в final bytes.
Case handling должно соответствовать existing qualification, а не отличаться
между research adapter и native route.

Два настоящих missing literal witness proposals здесь: `fastapi-02`
(`backgroundtasks`) и `fastapi-03` (`add_task`). Это найденный annotated факт,
но всё ещё не выполнение literal requirements текущего request contract.
Не объявлять такой отказ false negative только по наличию gold witness.

Synthetic test с `` `QueueTasks` ``: header не заменяет требуемый body literal.

## 3. Conditions: вопрос о времени ≠ условие применимости

`compile_need_contracts` / `_applicable_context` имеют ограниченную grammar.
На `fastapi-01`/`07` вся фраза `When do ... run ...?` попадает в constraint spans;
topic=True, но applicability unresolved. Это вопрос о времени выполнения, а не
автоматически recognized prefix `When feature is disabled, ...`.
`starlette-03` («Когда начинается lifespan teardown ...?») тоже topic=True,
condition unresolved. `uv-03` содержит настоящее scenario-condition, но current
grammar не установила applicability.

Нужный контракт:

- Известная scenario/state condition → current-window applicability или отказ.
- Temporal interrogative → не применять state-condition gate просто из-за When.
- Неподдерживаемая форма → explicit unknown, не silent applicable.
- Constraint одной независимой части bundled request → не blanket veto другой
  части; partial fact не сертифицирует private tail.

Это направления проверки, **не реализованный новый parser**. До изменения нужны
paired temporal/scenario examples, wrong-condition/negation mutations и retention.
Regex исключение только для `When do` здесь не добавлено.

## 4. Topic relevance: нет готового model-free replacement

Existing rule требует ≥3 terms и adjacent query pair в одной substantive sentence.
Найденный contextual fact может не повторять формулировку вопроса. Наличие BM25
hit не доказывает relevance. Удаление topic check уже приводило к sources во всех
8 unanswerable cases предыдущего diagnostic replay.

Следовательно, нельзя назначить topic=True потому, что source/subject/literals
прошли. Новому read contract по-прежнему нужны general positive/negative cases;
никаких proof/edit credits и relation-specific rescues.

## Дополнительное смешение: typed proof reason в read route

`httpx-06`: `verified_local_demand` — положительный reason typed admission, но
`read_context_admission` принимает только `visible_fields` / lexical refusal от
qualification и возвращает allowed=False. Это reason-contract mismatch.
Исправлять автоматическим разрешением строки нельзя: typed witness и read
context имеют разные обязанности. В новом интерфейсе нужны отдельные decisions,
не reuse proof decision как общего read veto или approval.

## Что делать дальше / что не делать

1. Сначала убрать case-handling divergence в **отдельном research candidate**,
   сохранив исторические probe/results. Не менять runtime под этот отчёт.
2. Описать independent trace decisions `source`, `subject`, `literal`,
   `applicability`, `topic`; refusal одного слоя не скрывает diagnostics остальных.
3. Проверить temporal-vs-condition и verified-owner subject на paired mutations.
4. Topic admission остаётся открытой исследовательской задачей. Не обещать,
   что decomposition сама решит recall/precision.

Production replacement остаётся остановлен, 01–04 сохранены. Budget не повышен.

## Проверки и артефакты

`artifacts/admission-layers-02/layers.json` и `summary.json` — корректная версия
independent normalized diagnostics. `artifacts/admission-layers/` — первоначальный
diagnostic run с тем же case bug; сохранён как история, **не использовать для вывода**.
Input — archived `grounded-budget-20261003-06`, hashes в прежнем provenance.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/admission_layer_probe.py --input /home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06 --output v2plan/artifacts/admission-layers-NEW
/usr/bin/python3.12 -m pytest -q tests/docs/test_grounded_budget_probe.py
```

Source-bound/forged-owner/body-literal tests добавлены в existing research module.
Проверки: **39 passed** (10 research tests + 29 API controls 01–04),
`git diff --check` без ошибок. Runtime files не изменены.
Этот документ уточняет attribution предыдущего отчёта, не пересчитывает quality
baseline и не делает прежний неполный safety checklist Green.
