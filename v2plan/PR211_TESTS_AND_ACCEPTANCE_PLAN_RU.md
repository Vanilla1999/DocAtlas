# PR #211: план сокращения тестов и завершения acceptance

Дата: 2026-10-09. База плана: `e4f0ae09221b80ba1afddf983a2a6e3001220c52`.
Статус: исполнение поручено владельцем 2026-10-09; исходный план опубликован в
`11489239ae0a5ff85c1f817f0650bea661e88ba1`. Выполненные пункты отмечаются только
после проверки соответствующего результата.

## Состояние исполнения на 2026-10-10

Последний полный фактический прогон — PR HEAD
`cadeef515ea78c78338821f38b15fed3bde7c993` (118), merge checkout
`9f25f147c522d84f61a57abb1d731d2b6e792c9a`, tree
`62d727c3ffbb35e77f0301d0e961e6f60ed4ebe2`.
На каждом Python 3.11/3.12/3.13:
**6065 PASS /1652 FAIL /0 ERROR /10 SKIP**, всего7727.
С113 исправлен mixed fixture control; collection прежняя.
Required CI/P1-stack exact остаются FAIL.

Critical теперь **54/54 healthy**, прямой producer step SUCCESS подтверждает
aggregate 29 intended kills. Recovery **12/12 и 33 kills** по stored summary.
Installed reviewed-wheel MCP **1/1**, self-test 7/7 и report verification PASS;
false-supported 0, contamination 0. Реальные client sessions **NOT RUN**.

P1.5 — **7/7**, facts 6/6, oracle 6/6. P1.4 — 12/14, discovery 8/10, facts 5/5.
P1.6 current 6/6; retained adversarial 24/28 и его mutation baseline FAIL.
Legacy source-fact acceptance 8/15 при floor 12/15, raw original coverage 0.
V2 natural facts 6/15 и paraphrase 1/5; REPORT_ONLY с production runner FAIL.

Reader 118 разобрал 326 records без ошибок, JUnit console omitted 0.
Artifact console: 128 selected / 51 printed / 77 omitted; все три compact V2 headers получены,
но все 29 individual critical mutant receipts отсутствуют в доступном console.
Retirement 33 DQP cases требует четырёх собственных named/source/import operands;
aggregate SUCCESS не заменяет их. Все 70 old DQP cases пока collected.

Reviewed119 добавляет relation25 precheck: 2 original plan calls и 1 directed
generation mutant,0 новых ordinary functions. Все 25 old cases остаются.
Reviewed120 приоритизирует actual critical/recovery operands и отмечает outcomes
четырёх существующих lossless cases. Own target: 54 healthy / 30 kills **PENDING**.
После proof возможны отдельные точные retirements 33 DQP и 25 relation cases;
unselected body/scope/condition/safety obligations сохраняются.

V2 source audit113 показал: все 3/1 qualified windows доходят до public, missing
cleanup/infrastructure facts отсеяны на qualification. Actual118 request-flow
даёт другой blocker: 27 готовых items сокращаются до 20 в control view, затем
budget_exceeded запрещает delivery. Product fix должен отделить эту границу
от реальных read/work/call/time bounds и сохранить consent/stale/current guards.

Подробные результаты и следующие действия:
[checkpoint](PR211_CHECKPOINT_RU.md),
[actual118](pr211-execution/RUNTIME_EVIDENCE_cadeef51.json),
[V2 source audit113](pr211-execution/V2_QUALIFIED_WINDOW_AUDIT_113_RU.md).
Исходные числа плана ниже остаются привязаны к своим историческим SHA.

## Поправки после оценки перед исполнением

- Первыми устраняются setup/contract причины, затем оценивается качество retrieval.
  Появление следующего падения после исправления fixture не означает регрессию само
  по себе, но требует расследования и не превращается в PASS.
- Разрешение выполнить план включает этап 4: прежняя отсрочка retrieval снята
  новым поручением. Исходные вопросы, факты и guards сохраняются.
- Сокращение каждого семейства зависит от его зелёного baseline и доказанного
  обнаружения дефектов. Не требуется ждать всего зелёного PR для уже стабильной семьи.
- Отмена output-cost потолков применяется согласованно к оставшимся активным
  downstream проверкам; operational work/read/call/time bounds сохраняются.
- Повторный CI оптимизируется отдельно и не задерживает исправление блокеров.
  Неустановленная причина остаётся открытой; она не считается завершённой миграцией.

## Цель и исходное состояние

Получить небольшой поддерживаемый набор проверок, который обнаруживает реальные
ошибки, и довести PR до прохождения всех обязательных проверок. Сокращать повторения
и стоимость исполнения; сохранять проверку исходной задачи, качества данных и guards.

- **Уже сделано:** фиксированный catalog ceiling 6144 bytes отменён; фиксированный
  retrieval-evidence ceiling 800 tokens удалён в `e4f0ae0`. Новый числовой потолок
  не вводится. Измерения объёма и стремление к минимуму сохраняются.
- На `e4f0ae0` [retrieval job](https://github.com/Vanilla1999/DocAtlas/actions/runs/37950861568/job/113888965198)
  SUCCESS. Все 80 результатов совпали с `fe48e7b` по payload/assessment/cost;
  все 17 оставшихся проверок соблюдены. Это изменение acceptance policy, не рост recall.
- Все 17 workflows `e4f0ae0` завершены: 8 SUCCESS / 8 FAILURE / 1 SKIPPED;
  [main CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/37950861568)
  и [P1](https://github.com/Vanilla1999/DocAtlas/actions/runs/37950861406) красные.
- Последний независимо разобранный полный core JUnit относится к **`fe48e7b`**:
  на каждом Python 3.11/3.12/3.13 — 8513 случаев, 6506 PASS / 1936 FAIL /
  61 ERROR / 10 SKIP. Это не новый подсчёт для `e4f0ae0`.
  [Предыдущий прогон](https://github.com/Vanilla1999/DocAtlas/actions/runs/37888242626).
- Инвентаризация кода: 4955 определений тестов, 917 `parametrize`, без Hypothesis.
  Число определений, развёрнутых случаев и фактических исполнений учитывать отдельно.

## Что берём из статьи

[Countdown-Code, arXiv:2603.07084v3](https://arxiv.org/html/2603.07084v3)
показывает расхождение между доступной агенту проверкой и правильностью относительно
исходной задачи. Статья не доказывает, что unit-тестов должно быть меньше, и не является
исследованием property-based testing. Наше применение: независимый oracle, исходные
входы и требования, проверки преобразований и намеренно внесённых дефектов.

Целевая структура: обычные тесты для точных контрактов и опасных границ; сценарии
через публичный API/MCP; проверки свойств и преобразований; mutations, доказывающие,
что эти сценарии замечают ошибку. Существующий task-level evaluator расширяем
(`eval/task_level/_execution_part02.py`, `eval/task_level/evaluators/task_contract.py`,
`eval/task_level/fixtures/builder.py`), отдельный параллельный framework не создаём
без необходимости.

## Пакеты работ и критерии завершения

### 1. Карта падений и независимый критерий правильности

- [ ] Сопоставить все оставшиеся FAIL/ERROR core и downstream с первой причиной:
  устаревший контракт, неверная fixture, дефект evaluator, дефект продукта либо
  причина ещё не установлена. Начать с имеющихся JUnit/logs; перед изменением
  семейства сверить его evidence с текущим кодом и SHA.
- [ ] Для каждого семейства записать: исходная задача → действующее правило →
  положительный/отрицательный сценарий → меняемый файл → проверка результата.
  Не считать все оставшиеся падения автоматически «legacy».
- [ ] Зафиксировать исходные вопросы, обязательные факты, допустимые источники,
  scope/generation и изменения состояния. Oracle не выводит ожидание из ответа
  production-кода. Его согласованная версия и эталонные данные находятся вне
  доступной оцениваемому агенту поверхности изменений; их миграция видна отдельным
  diff и проходит независимое review. Одних hashes внутри того же изменяемого
  patch недостаточно.

**Готово:** у каждого падения есть группа и следующий шаг либо явный статус
«не исследовано»; у первого исправляемого семейства есть проверяемый текущий контракт.
Полнота карты не заменяет устранение падений.

### 2. Исправить fixtures и мигрировать действующие публичные контракты

Две линии можно вести параллельно при раздельном владении файлами.

| Линия | Что сделать | Проверка результата |
|---|---|---|
| Question / hermetic | В `run_question_surface_gate.py` и quality protocol сохранить исходные 100 вопросов; отделить честные unresolved/missing от ошибки классификации `silent_empty`. Убрать ожидания отменённых автоматических NL intents/proof/aliases только по карте контрактов. | Известный положительный пример возвращает полезные source-bound данные. «Всегда пусто», «всегда unknown» и выдуманная полнота не проходят. |
| Recovery | В `run_recovery_contract_gate.py` разобрать no candidates, ineligible evidence, operational recovery и conflict. Для пустых candidates проверить смысл `retrieval_miss/no_candidate_evidence`, затем остальные assertions и mutant anchors. | Положительный сценарий проходит через подтверждённый member и текущий публичный вызов; причины отказа различимы, consent/source binding и отсутствие auto-execute сохранены. Замены одного слова `parsing` недостаточно. |
| Agent Developer / adversarial | Исправить подготовку `eval/agent_developer_v1/projects/`, tasks/trajectories и gate runners: конечный явный docs catalog, корректное подтверждение membership и host storage. Общий `index_project` менять только при доказанной общей проблеме. | Весь protocol доходит до поведенческих проверок и отчёта. Сценарий без catalog остаётся отрицательным; отдельный positive явно подтверждает membership. Неоднозначность двух module paths не разрешается скрытым выбором. |

Для `autodiscovery_module_supported` нельзя просто добавить catalog и назвать это
прежней проверкой: оформить преемника positive и сохранить запрет implicit discovery.
После устранения setup-проблем разобрать следующие причины, а не объявлять весь gate
зелёным. Те же правила применить к остальным семьям из карты пункта 1 небольшими slices.

**Готово:** затронутые contract baselines проходят positives и negatives без setup
errors. Если следующий барьер оказался реальной потерей retrieval, gate остаётся
незакрытым и получает зависимость от пункта 4.

### 3. Согласовать docs → catalog → quality oracle

- [ ] Подтвердить поддерживаемые пользовательские факты и документацию, затем
  привести в соответствие `docs/INDEX.md`, `docatlas.project-docs.yaml` и quality cases.
  Разобрать четыре неактивных witness paths: `wiki/Commands.md`,
  `docs/modules/project-context-retrieval.md`, `docs/index-cleanup.md`,
  `docs/modules/evidence-selection.md`.
- [ ] Документ включается в catalog по продуктовому смыслу. Альтернативный witness
  должен подтверждать тот же факт. Миграцию `cases.json`, crosswalk и protocol/
  acceptance locks в `eval/project_context_quality_v2/` проверить независимо;
  исходные вопросы и отрицательные требования не ослаблять.
- [ ] Получить собственный полный V2 runtime-отчёт после corpus validation.
  Появление JSON само по себе не означает прохождение quality.
- [ ] В Legacy применить принятый ADR 0003 через отдельную версионированную
  миграцию acceptance: минимум 12 из 15 исходных положительных cases с полными
  frozen facts в реально возвращённых допустимых source windows. Независимо
  проверять same-call snapshot, текущие bytes/hash, host-selected root, scope и spans.
  Raw `original_query_covered_count` сохраняется отдельной метрикой: lookup hits
  не получают original credit. Это явная смена смысла блокирующей метрики, а не
  сохранение прежнего raw-coverage gate под новым названием. Frozen вопросы,
  обязательные факты и шесть hard-zero safety gates остаются. Code/review готовы
  в `34913345f8f6f491fc707a9028c58d7d68319cd5`; новый runtime PENDING.
  [Crosswalk и обоснование](pr211-execution/LEGACY_SOURCE_FACT_ACCEPTANCE_RU.md).
  Предыдущее доказанное полное покрытие фактов 8/15 ниже 12/15; quality не объявлен PASS.
- [ ] Для contamination проверить нужный факт `doc-atlas mcp docs-serve` и реальную
  подмену Docs на Packs. В зафиксированном случае вернулся неподходящий фрагмент
  `PROJECT_MAP.md`; слово `packs` само по себе не доказывает выдачу или исполнение
  `packs-serve`. Уточнить oracle, сохранив отрицательную проверку подмены.
- [ ] Исправить устаревшие обещания proof/budget в поддерживаемых README/MCP docs;
  измерения 800 в исторических отчётах не переписывать как новые результаты.

**Готово:** gold ссылается на действительные источники того же факта, V2 исполняется
до конца, Legacy отдельно показывает original coverage и contamination. Оставшиеся
потери качества видимы и имеют причину в acquisition/qualification/selection/delivery.

### 4. Отдельный возврат к реальным проблемам retrieval

Владелец включил этот этап в реализацию поручением выполнить план от 2026-10-09;
позднейшее решение записано в [current decisions](CURRENT_WAVE_DECISIONS_RU.md).
[Deferred analysis](after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md) остаётся исходным
диагностическим материалом, а его прежняя отсрочка больше не блокирует реализацию.

- [ ] После пункта 3 повторить исходные RU/EN вопросы и локализовать потери:
  original-only paraphrase; multi-section/long selection; admission полезных partial facts.
- [ ] Исправлять только подтверждённую границу потери. Не предполагать заранее,
  что нужны embeddings, новый provider или загрузка модели.
- [ ] Проверять сохранение доступных обязательных фактов, условий и длинного хвоста;
  partial выдаёт известное и честно отмечает неизвестное. Сохранять unrelated/absent
  negatives, source/catalog/hash/span/current/consent guards.
- [ ] Стоимость полного model-visible DTO и catalog измерять и сокращать без
  фиксированных ceilings 800/6144 и без потери полезных фактов или guards.

**Готово:** исходные позитивы и негативы соблюдены через настоящий delivery,
original coverage не подменена lookup credit. Если этот этап нужен для обязательного
красного gate, его отсрочка не делает PR готовым к merge.

### 5. Доказать силу проверок и сократить повторения

- [ ] После зелёного baseline целевого protocol усилить
  `run_recovery_mutation_gate.py` и `run_agent_developer_adversarial_mutation_gate.py`
  по образцу действующего critical gate: известный roster, ожидаемый assertion,
  подтверждённый изменённый/исполняемый модуль, отсутствие errors и необъяснённых skips.
  Import/setup crash, timeout, произвольный nonzero exit и mutation без эффекта
  не считаются успешным обнаружением дефекта.
- [ ] Начать сокращение с 288 unknown-tail случаев в
  `tests/docs/test_question_span_coverage.py` и 399 случаев
  `tests/test_dictionary_exit_legacy_compilers.py`. Это кандидаты на анализ повторов,
  не доказанные 687 лишних тестов. У второго семейства есть разные API и проверки.
- [ ] Составить матрицу «свойство → старые случаи → контрпример/дефект → новая проверка».
  Повторы заменить компактными проверками свойств и преобразований. Сохранить API,
  Unicode/quotes/whitespace, исходные offsets, unknown tail и отдельную lookup lineage.
- [ ] Добавлять варианты с независимыми ожиданиями: нерелевантный документ не создаёт
  поддержку ответа; чужой scope не поставляет evidence; stale generation не разрешает
  запись; удалённый необходимый факт перестаёт считаться найденным. Преобразование
  строки должно иметь заранее определённый смысл, а не обещать любую перефразировку.
- [ ] Сравнить старый и новый набор на исторических контрпримерах и целевых mutations.
  Сохранять найденные минимальные контрпримеры. Для широких генерируемых/отложенных
  примеров предусмотреть отдельный воспроизводимый прогон; обязательные свойства
  остаются в PR-проверке. Новую зависимость не вводить ради переименования тестов.
- [ ] Удалять старые случаи только после зелёного baseline соответствующей семьи и
  доказательства обнаружения её дефектов новым набором. Не включать 109 transaction/
  security случаев `test_mcp_delivery_member_transaction.py` в первый пакет сокращения.

**Готово:** меньше поддерживаемых повторов и измеренная стоимость исполнения при
сохранении значимых свойств и дефектов. Перенос 288 итераций внутрь одной функции
не считать сокращением работы. Отдельно показать definitions, expanded executions,
время и обнаруженные дефекты; не вводить произвольную квоту на число тестов.

### 6. Убрать дублирование core CI отдельным изменением

- [ ] В `.github/workflows/ci.yml` и `.github/workflows/p1-stack-exact-validation.yml` заменить повтор
  одинакового core на Python 3.11/3.12/3.13 одним проверяемым источником результатов,
  сохранив оба обязательных aggregates и возможность самостоятельного P1 запуска.
- [ ] Reuse допускается при совпадении checkout/merge tree, Python/runtime и
  dependencies, версии проверки/selection, полного JUnit roster и успешного producer
  run/attempt. Если подходящего результата нет, P1 запускает producer.
- [ ] Проверить, что чужой SHA, stale/partial artifact, отсутствие evidence и SKIP
  не дают PASS. Двойной вызов общего `workflow_call` сам по себе повтор не устраняет.

**Готово:** один эквивалентный core действительно исполняется один раз, обязательные
проверки сохранены, экономия подтверждена измерением. Это оптимизация; её можно вынести
из merge-critical последовательности, если она задерживает исправление блокеров.

### 7. Совместный acceptance на конечном SHA

- [ ] На одном конечном SHA/проверяемом merge tree получить полный core,
  advanced, required CI/P1 и все обязательные downstream результаты.
- [ ] Сверить состав случаев и объяснить все удаления/миграции gold; отсутствие
  прежней проверки или отчёта не превращается в PASS.
- [ ] Повторить необходимые installed-package, MCP transport, restart/CAS и platform
  сценарии. Только разрешённые fixture-only Git/server subprocesses; без изменений
  пользовательских индексов, скрытых provider calls или downloads.
- [ ] Закрыть необходимые реальные client checks либо явно указать конкретный
  недоступный обязательный запуск. SDK/scripted harness не подтверждает работу
  настоящих Claude Code/Codex/OpenCode. Сейчас эти реальные sessions NOT RUN.
- [ ] Обновить checkpoint: SHA, required checks, runtime/client evidence, оставшиеся
  ограничения и измерения стоимости. Готовность к merge заявлять только после
  выполнения обязательных критериев; сам merge остаётся отдельным действием.

## Порядок исполнения

1. **Ближайший узкий пакет:** карта актуального question/recovery контракта и
   миграция его positives/negatives (пункты 1 и 2), отдельный commit и review.
   Общую карту оставшихся core/downstream причин вести одновременно.
2. **Параллельно:** Agent Developer/adversarial fixtures из пункта 2 и согласование
   docs/catalog/quality из пункта 3. Один ответственный за каждый общий файл.
3. **После зелёных целевых baselines:** строгие mutation controls, затем первое
   сокращение двух стабильных семейств из пункта 5. Реальные retrieval blockers
   направлять в разрешённый пункт 4, сохраняя исходные задачи и quality guards.
4. **Отдельно:** оптимизация CI из пункта 6; затем обязательный совместный acceptance.

Каждый пакет: небольшой diff → независимое review смысла контракта → целевой прогон
через разрешённый CI → обычный fast-forward в существующий PR. Полный прогон нужен
на конечном SHA и при конкретной необходимости проверить общую регрессию;
не запускать дополнительные копии того же набора без оставшегося вопроса.

План не вводит дату merge, новое число «достаточных тестов», новые output ceilings
или автоматическое ослабление quality gates. Объём реализации уточняется по первой
доказанной причине каждого оставшегося падения.
