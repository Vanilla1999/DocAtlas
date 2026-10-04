# Harness исправлен; неизменённый candidate REJECTED

## Что разрешено и изменено

Отдельное разрешение пользователя после `dd0dd441`: исправить только test DTO
boundary/logging, получить working source-eligibility positive, затем один
содержательный I.3 run на неизменённом алгоритме. Обнаруженные algorithm defects
не исправлять внутри замера. Старые invalid artifacts сохраняются без изменений.

Изменён только `v2plan/test_next07_grounded_first.py` и журнал текущего плана;
создан этот новый каталог. Candidate/ports, runtime, исходный LeaseClient fixture,
frozen expectations и чужая dirty работа не менялись. Hashes до/после — protocol,
pre-run manifest и result.json. Полный тестовый harness заморожен перед run в
`frozen-harness.py`; дополнительные algorithms отсутствуют.

## Исправленный переход

1. Existing isolated service индексирует неизменные source bytes.
2. Observer сохраняет source-reference-prepared inventory **до native removal**.
3. Существующая функция `proposals` задаёт один I.2 order и whole original spans.
4. Whole windows переподготавливаются через исходный `SourceReferenceContext.prepare`.
5. Scoped research replacement передаёт эти windows в настоящий
   `get_project_docs`, не в обход его current catalog/hash/lifecycle checks.
6. Настоящий `ProjectDocsChunk` проходит `project_context_pack`; оттуда берутся
   source_class, scope, authority, freshness, identity и snapshot metadata.
7. На этом DTO материализуются whole original quote и `char_span` по его
   `char_start/char_end`. Никакого ручного `project_file → project_doc` нет.
8. Каждый original read DTO проходит eligibility и проверку raw slice прежде
   candidate decision. Damage controls затем меняют ровно один фактор.

Это локальный I.2→I.3 harness, не MCP delivery, не новый public schema и не
переключение production policy. Проверка полной retrieval inventory/general
retention по всему corpus не выполнена.

## Smoke и единственный содержательный run

Первый smoke остановился в evidence logger: `ProjectDocsResult` — dataclass,
не объект с `model_dump`. Output сохранён в `smoke-command.json`. Исправлен
только logger (`asdict`), успешный контроль — `smoke-repaired-command.json`.
Default row: `project_doc`, span `[0,50)`, current snapshot, точные исходные bytes;
eligibility проходит, decision разрешён как retrieval-only unknown applicability.
Это исправление harness по явно разрешённой работе, не изменение candidate.

Команда единственного содержательного run:

```sh
DOCATLAS_OFFLINE=1 NEXT07_CONTROL_OUT=<этот-каталог>/controls \
  .venv/bin/python -m pytest v2plan/test_next07_grounded_first.py -q \
  --junitxml=<этот-каталог>/tests.xml
```

Точные argv/env/exit/stdout/stderr — `tests.json`, JUnit — `tests.xml`.
**22 PASS / 2 FAIL**, exit 1. Из 22 PASS: 8 I.2, 2 LeaseClient read positives,
12 actual mutation negatives. Mutation tests прошли working positive и
выполнили negative calls; `result.json` содержит все observed rejection reasons.
Все 32 decisions записаны в `controls/decisions.jsonl`; immutable sources,
ranked proposals, omission records, ProjectDocsResult и actual read DTO —
`controls/preparation.jsonl`.

### Содержательный failure 1: wrong-state

Вопрос: `What is OrbitClient default timeout when preview is disabled?`

Short disabled positive разрешён. На исправном `project_doc` допускается negative:

```text
# OrbitClient

When preview is enabled, OrbitClient default timeout is 7 seconds.
```

Actual decision: `allowed=True`,
`source_bound_retrieval_only_unknown_applicability`. Eligibility успешно проверена
до этого вызова. Заявленная ветка `existing_local_condition_mismatch` не сработала:
matcher `relation_local_witness` не обслуживает operator `default`. Это observed
local failure и согласованный code-derived диагноз, не harness-проблема.

### Содержательный failure 2: позднее ограничение

Short source positive с той же restriction допускается и сохраняет её.
На boundary fixture existing source содержит fact, длинный промежуточный абзац и
строку `Only when an operation expires.`. Actual allowed fact window `[0,51)`:

```text
# LeaseClient

LeaseClient raises `LeaseExpired`.

```

Restriction отсутствует. Теперь тест не проходит за счёт arbitrary refusal:
есть working short positive, eligible boundary input и записан actual decision.
Whole unit и existing dependency edges оказались недостаточны для preservation
этого source constraint. Новый regex/parent rescue не добавлялся.

## Итог по шаблону плана

- **Branch / baseline / candidate:** `next07-feasibility-audit`, HEAD `dd0dd441`
  + прежний dirty patch (`baseline.patch`). Algorithm bytes идентичны этому HEAD;
  изменился только harness. Эта работа не коммитила и не пушила новые изменения.
- **Последний шаг:** валидная local I.3.
- **G actual package run:** прежний DONE, hashes reference artifacts проверены;
  без повторного запуска.
- **C final packet:** NOT_RUN.
- **Часть I:** REJECTED текущего неизменённого candidate.
- **Часть II:** NOT_RUN.
- **P1/P2/P3:** local read positives доставляют owner/default `17/29 seconds` и
  expired-operation clauses `LeaseExpired/WaitExpired`. Final C и P3 NOT_RUN.
- **Recovered / lost / retained IDs:** native recovery, 49-ID/partial retention
  NOT_RUN. Partial local result не объявляется native recovery.
- **Hard guard / budget / span:** 12 перечисленных mutation guards измерены на
  корректных positives. Wrong-state и restriction preservation FAIL. Final C
  budget/source cap/span validator NOT_RUN. Runtime hashes неизменны.
- **Policy conflicts / old failing nodes:** старые tests/gold не менялись;
  required regression/full suite не запущены после failing local acceptance.
  Прежние blockers 06 остаются открытыми.
- **Unseen / reader:** NOT_RUN.
- **Заменённая ответственность:** только harness conversion; read algorithm,
  ranking/splitter, guards и production owner не изменены.
- **Files / commands / artifacts:** изменённый research test и plan journal;
  protocol, pre-run code/runtime hashes, smoke outputs, controls, tests JSON/XML,
  result и этот отчёт в новом exclusive directory.
- **Not_run:** I.4–I.6, II, остальные controls, native final packet, retention,
  required gates/full suite — STOP после двух содержательных failures.
- **Следующий шаг:** отдельное решение о версии candidate, заменяющей явно
  названные wrong-state/preservation обязанности. Не исправлять автоматически;
  текущий candidate не принят, rollout запрещён.
