# Исполнение сокращения: актуальный baseline c518359f

## База и сохранение работы

- Исходники: `c518359fbf09f3a7c7457d686682bf3e12eecfae`.
- Handoff и правила сохранены отдельным коммитом `ec618e85`.
- Актуальный CI: [38030248861, attempt 1](https://github.com/Vanilla1999/DocAtlas/actions/runs/38030248861).
- Checkout merge: `2d618e3b3cd92b5d86f252c9e742d1aac52a562e`.
- Merge и исходный HEAD имеют одинаковый tree: `8f6b492ecdeb034a9e580221ba22343feea599b5`.
- GitHub API доступен; credentials и permissions не менялись.

## Полный roster, не сумма повторных исполнений

| Набор | Всего | PASS | FAIL | SKIP |
| --- | ---: | ---: | ---: | ---: |
| Core | 7669 | 6070 | 1589 | 10 |
| Advanced | 622 | 528 | 94 | 0 |
| Unique core+advanced | **8291** | **6598** | **1683** | **10** |

Полные JUnit распарсены независимо от проекта стандартным XML parser; core
сверен с готовыми поузловыми CI diagnostics. У каждой lane нет повторных
identities; core roster и outcomes совпадают на Python 3.11/3.12/3.13.
Пересечение core/advanced пусто. Failure messages разных Python lanes могут
различаться; равенство сообщений не заявляется. Setup errors отсутствуют.

Цель полного набора: `ceil(0.40 * 8291) = 3317` net removals;
остаток с новыми проверками максимум **4974**. Отдельная цель core остаётся
3068 net removals / максимум 4601. Live и standalone gate executions отдельно.

Доказательства:
- `TEST_REDUCTION_40_BASELINE_c518359f.json`: параметры CI, полные JUnit hashes,
  suite counts и время каждого producer.
- `TEST_REDUCTION_40_ROSTER_c518359f.json.gz`: все 8291 expanded node IDs,
  per-node outcomes и failure messages одной core lane плюс advanced.
- `TEST_REDUCTION_40_MANIFEST.json`: единый поузловый family manifest;
  `UNRESOLVED` не является разрешением удаления.
- `TEST_REDUCTION_40_RUNTIME_c518359f.json.gz`: exact 226 CI artifact records;
  compressed SHA-256 `8b874953601e4fe92855840ded93192ab1af04848e5cfc05985c799fd7bafd0f`,
  исходный SHA-256 `877699e9dc226158fe75023c39581becc526443118b924f627252f6d66330bff`.

## Продуктовые и доказательные блокеры

- Critical healthy baseline: **62 PASS / 0 FAIL / 0 ERROR / 0 SKIP**.
  До остановки gate записан **41 validated intended kill**. Bare-locator
  mutation вызвала правильный semantic predicate, но сообщение assertion
  имело форму tuple вместо точного guard. Исправление сообщения отдельно;
  ожидания, inputs и predicate не меняются. Нового mutation credit пока нет.
- Role19 требует собственных 43 kills и других условий; пакет заблокирован,
  полный зелёный critical baseline сам по себе не разрешает его удаление.
- Recovery: **11 PASS / 1 FAIL / 0 ERROR**;
  `closed_literal_context`, guard `recovery_pair_original_unresolved`.
  Mutation gate не даёт 46-kill proof при красном healthy baseline.
- Legacy: **2/15** independently verified original-case full facts при floor12;
  raw original coverage0, contamination count1. Новая строгая метрика не
  сопоставляется напрямую с прежним менее строгим фактическим подсчётом.
- V2: natural **8/15**, paraphrases **2/5** verified full semantic coverage;
  production runner FAIL. Текущие факты не подменяются историей CI136.
- Required CI и P1 stack FAIL. Installed scripted smoke не является реальной
  клиентской сессией; Claude Code/Codex/OpenCode sessions **NOT_RUN**.

## Работа в процессе

Три независимых read-only аудитора A/B/C выполнили первоначальную классификацию.
В следующем узком пакете A проверяет собственный current proof QP26/DQP1;
B отделяет отменённые physical-project-prune/generated-alias expectations.
Другие кандидаты не удаляются без crosswalk и необходимого evidence.

Host-level трасса `DOCATLAS_TRACE=0|1` подготовлена к review: startup setting,
scoped private diagnostic runner, отключение decision/upstream preview collection
в OFF, безопасный отдельный stderr sink в ON. Один новый настоящий integration
проверяет OFF→ON→OFF, source payload/snapshot, независимый факт и число retrieval
calls на реальном isolated indexed corpus. Это in-process proof, не installed
stdio или client proof. Локальное исполнение проекта запрещено checkpoint;
runtime acceptance этих изменений остаётся **NOT_RUN** до разрешённого CI.

Повторный core в CI/P1 ещё не устранён. Цель −40% не достигнута;
runtime calls/mutations вне сохранённых receipts и конечное время **NOT_MEASURED**.
Окончательное число removed/added и FINAL_SHA публикуются после интеграции,
review и собственного CI, а не выводятся из статических кандидатных объёмов.
