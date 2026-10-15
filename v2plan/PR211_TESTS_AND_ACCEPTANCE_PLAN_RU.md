# PR #211: план сокращения тестов и завершения acceptance

## Уточнение владельца от 2026-10-10

Новые проверки — только интеграционные и выше; существующий набор требуется
существенно сократить. Приоритет — исходный вопрос через production-путь,
конечная выдача и включаемые/выключаемые диагностические логи.
[Актуальная стратегия и разбор статьи](TEST_STRATEGY_INTEGRATION_FIRST_RU.md),
обязательные правила — в корневом `AGENTS.md`. Прежнее предложение расширять
обычные unit/helper проверки заменено этой стратегией. Исторические результаты
ниже и условия сохранения источников/полномочий остаются действительными.

Дата: 2026-10-09. База плана: `e4f0ae09221b80ba1afddf983a2a6e3001220c52`.
Статус: исполнение поручено владельцем 2026-10-09; исходный план опубликован в
`11489239ae0a5ff85c1f817f0650bea661e88ba1`. Выполненные пункты отмечаются только
после проверки соответствующего результата.

## Состояние исполнения на 2026-10-10

Последний завершённый CI — PR HEAD
`a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07` (136), merge
`32765e44d2e85d3f638ac9d22a2fa6f4f46f6aee`, общий tree
`7f663bac25aa6e79c48a07301d2e94e5e7352c42`.
На каждом Python3.11/3.12/3.13:
**6052 PASS / 1607 FAIL / 0 ERROR / 10 SKIP**, всего7669.
Collection прежняя, FAIL на15 больше130. Их причины разбираются отдельно;
required CI, P1 stack и closure остаются FAIL.

- P1.4: **14/14 cases, 10/10 discovery, 5/5 complete facts**, oracle5/5,0errors.
- Recovery: **12/12 healthy, 43/43 intended kills**. Все43 outcomes сверены
  по case/guard/count; полный независимый source/import rehash всех43 не заявляется.
- Critical: **61entries,1observed FAIL** на existing retention completion.
  Default surface отклонял context_format до handler.39mutants не выполнялись;
  свойство остальных60entries не выдаётся за PASS без раскрытого skip count.
- Literal comparison: **702/702 historical и82/82 compact**, aggregatePASS.
  Из104child receipts51faults доступны87: все87 проверены индивидуально,
  включая15 exact source blobs и actual import identity.17 не попали в console.
  Default уже compact; `activated_compact_default=false` означает, что
  comparison runner не менял default, а не что702cases всё ещё default.
- Read_next: **23/31 PASS,8FAIL**. Новые failures требуют прежнего продолжения,
  raw source/span fidelity и authorization; expected read_next==1 сохранено.
- Installed: **7/7 selftests,1/1 scripted task**, reviewed-wheel,
  report verificationPASS. Реальные Claude Code/Codex/OpenCode sessions NOT_RUN.
- P1.6: public6/6,full facts1/1,oracle6/6; общий jobFAIL,
  adversarial24/28. Retrieval/platforms/P1.5SUCCESS.
  Legacy/V2/Agent quality stepsFAIL; текущие summaries не попали в console.
  Последние прочитанные числа130 — Legacy8/15,raw original0,
  V2natural6/15/paraphrase2/5,AgentV1closed8/11 — остаются историей130.

[Receipt136](pr211-execution/RUNTIME_EVIDENCE_a9fba17d.json) сохраняет431
parsed records без parse errors,43 recovery outcomes,87 individual literal
audits и exact missing17. Reader145 отдаёт quality summaries раньше тяжёлых
records и показывает явные omissions. Product output ceilings не возвращаются.

Reviewed follow-up137–150 собран; собственный совместный runtime **PENDING**:

| Slice | Изменение |
| --- | --- |
|137/142|Global иAgent fixture oracles сохраняют настоящие LF/CRLF bytes; line bounds и negative controls остаются.|
|138/144|Exact QP26 audit; все19 исходных role questions,2resolver cases и2directed faults. Удалений ещё нет.|
|139/140|Новые qualified source units не теряются после lookup coverage; native24 inventory, duplicate/reverse controls; pending recipe rebase.|
|141/143|Шесть retention migrations сохраняют полный source set/guards; explicit advanced public surface проверяет missing completion.|
|145/147|Доступные individual receipts/quality summaries и independently reviewed actual136 record.|
|146/148|Structural window сохраняет raw text и согласованные char/UTF-8/line bounds;8 continuation scenarios с прежним authorization.|
|149|Оба буквальных имени сравнения в одном source paragraph; исходный вопрос неизменён, answer/edit authority не выдаётся;3directed faults.|
|150|Private diagnostics различают final validated payload, core/primary/hint и реальные decision events, не меняя selection или scorer.|

Следующий joint target: **critical62 healthy/43 intended kills;
recovery12 healthy/46 intended kills**. Ноль новых pytest names не означает
ноль дополнительных внутренних операций: стоимость перечислена в owning notes.

Существующее retirement58 подтверждено собственным121 proof. Подготовлены
ещё46 exact removals: QP26 с2keepers, один DQP default3/800 case,
reference-role19 ссохранением21othercases иnative matrix24.
Они остаются live до собственных healthy successor/intended kills и
проверки helpers/imports/selectors; текущий static review это не заменяет.
Remaining relation47 также сохраняются до отдельного proof.

V2flow136 даёт18 public sources, но old private final-ID preview только3.
После core идут joint/query finalizers; этот preview не доказывает потерю15
sources. Новый observer должен показать действительный first veto недостающего
window. Далее исправляются реальные frozen facts/original-only/paraphrase/
comparison gaps с отдельными contamination и authority guards.

[Checkpoint](PR211_CHECKPOINT_RU.md) ·
[решения](CURRENT_WAVE_DECISIONS_RU.md) ·
[actual130](pr211-execution/RUNTIME_EVIDENCE_0065ce62.json) ·
[retirement58](pr211-execution/COMPILER_RETIREMENT_58_RU.md) ·
[original input](pr211-execution/PROJECT_READ_ORIGINAL_INPUT_RU.md) ·
[raw window](PR211_LITERAL_RAW_WINDOW_BINDING_RU.md) ·
[final carrier](PR211_FINAL_PROJECTION_OBSERVATION_RU.md).
Исходные числа плана ниже сохраняются как история своих SHA.

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
