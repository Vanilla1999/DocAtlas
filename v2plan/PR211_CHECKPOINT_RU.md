# PR #211: checkpoint продолжения merge-readiness

## Последний полный прогон: 991638f; member/mtime и self-host setup

Обновление: 2026-10-08. Полный [CI 37840422988](https://github.com/Vanilla1999/DocAtlas/actions/runs/37840422988)
завершён на HEAD `991638f28ecff659c320b45738edfaa8b9fd375e`, merge checkout
`e499c39704d4923164dc50c1460a2e1c50b81d7f`, tree
`955bac94d5ca6b847f558b0e7dbd0dcb8265e9df`. Все 25 опубликованных файлов сверены
с reviewed bytes; четыре commits — обычный fast-forward обеих веток.

- Python 3.11/3.12/3.13: **8513 = 6496 PASS / 1946 FAIL / 61 ERROR / 10 SKIP**.
  Полные concrete roster и outcomes одинаковы. Против 04ff ровно **7 FAIL→PASS**,
  добавлены шесть новых self-host nodes: пять PASS, один FAIL. Удалений и прежних
  PASS regressions нет. Реконструкция полного roster из baseline + delta точная.
- Семь из восьми member/read/mtime targets прошли, включая foreign same-path,
  hash-first stale reads, exact descriptor mtime и mtime-only touch без read writes.
  Module manifest target прошёл explicit sync, но сохранил FAIL уже на public
  `insufficient_evidence / required_evidence_missing`; исходные вопросы не изменены.
- **141/141** member/descriptor/trusted-storage/hash/CAS controls PASS в каждой Python.
  Из 2006 старых nodes с прежним FAIL/ERROR у десяти первый barrier прошёл дальше:
  module manifest и девять self-host downstream consumers. Остальные 1996 первые
  причины прежние; 47 diagnostic ERROR сохранили exact messages и barriers.
  Эти десять advances не являются PASS или исправлением deferred retrieval.
- Пять новых self-host safety tests PASS: полный tracked mirror/config/hash
  fidelity, точный catalog membership с physical distractors, cold no-grant,
  conflict/hash/CAS отказ до записи и environment/original preservation.
  Шестой test прошёл cold/prepare/generation/store guards, затем получил public
  `status=insufficient_evidence`. JUnit содержит только status; reason/kind и полный
  DTO этого нового node не раскрыты, CRLF failure не установлен.
- Advanced: **622 = 524 PASS / 98 FAIL**, прежние roster/states. Девять независимых
  downstream steps фактически FAIL; dependent adversarial mutation SKIP после
  красного baseline. Critical baseline **19/28 PASS**, mutants не стартовали.
- Legacy self-host JSON подтверждает **2807 tracked files / 119478143 bytes**, exact
  merge/tree, cold_read_verified=True, **10 members / 98 sections**, zero deletions
  и origin_unchanged_after_calls=True. Теперь **10/16 cases PASS**; оставшиеся
  frozen floors включают original_query_coverage **0 < 12** и contamination count 1.
- V2 остановился на validate_corpus: `witness is not an active catalog document:
  wiki/Commands.md`. Его JSON/provenance не создан; собственный V2 prepare не
  объявляется доказанным только из порядка вызовов. Catalog/gold не подменялись.
- Все **6 platform SDK jobs PASS**. Main package/CLI **77/77** на Ubuntu, macOS ARM
  и Intel. Проверены **19 logs / 15 SDK invocations / 30 lanes / 420 observations**;
  source bindings и outcomes совпадают с 04ff. Во всех 30 restart/repeat lanes
  derived_writes=0, stale-null CAS rejected, source/generation rows unchanged.
- Installed scripted harness **1/1 PASS**. Release build, три wheels,
  sdist/installer и required-release **PASS**; публикация release SKIP.
  Actual Claude Code/Codex/OpenCode sessions **NOT RUN**; SDK не заменяет эти apps.
- Все 17 workflows completed: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**. Required CI
  **113532153123 FAILURE**, P1 aggregate **113532324954 FAILURE**.

Catalog source не менялся: прежние **6918 bytes**, docs output schema **860 bytes**.
Владелец снял fixed catalog ceilings; продолжается минимизация с сохранением guards.
Отдельные output <1000 и frozen retrieval 800 сохранены. Все 80 BPE values прежние,
80/80 canonical UTF-8 byte measurements сверены; max **1451** и **24/48** within-budget
cases выше 800. Это pinned offline BPE, не цена actual app/model sessions.

[Полный acceptance 991638f](PR211_991638F_ACCEPTANCE.json) содержит завершённые jobs,
actual runtime, downstream/Legacy provenance и границы утверждений.
[Core delta](PR211_991638F_CORE_ACCEPTANCE.json) содержит все семь transitions,
шесть новых состояний, три JUnit bindings и security/first-barrier comparison.
Исторические reports ниже не переносят PASS на последующие commits.

### Следующий узкий successor нового synthetic positive

Source review установил самостоятельный literal qualification blocker: исходный
вопрос ``What does `MirrorNeedle` require?`` даёт четыре raw terms; в прежнем RULES
совпадает только MirrorNeedle. require не равен requires по текущему контракту,
1/4 < 0.4. Это source-grounded blocker, не восстановленный hidden CI reason.

В новом fixture test сохраняются исходные question, RULES/CRLF и все source/hash/
snapshot/storage guards. Только prepared public call получает отдельно заданный
host lookup `` `MirrorNeedle` explicit preparation ``. Lookup должен иметь собственный
credit, не credit query-original; answer/edit authority остаются False. Это
synthetic lifecycle/read-wiring positive, не исправление original-question quality.
[Author review](PR211_SELF_HOST_LITERAL_LOOKUP_REVIEW_RU.md) и
[independent review](PR211_SELF_HOST_LITERAL_LOOKUP_INDEPENDENT_REVIEW_RU.md).
Runtime этого successor **NOT RUN** на момент записи; следующий actual CI проверяется
на новом HEAD после обычного push. Frozen downstream questions/corpus/scoring,
production retrieval и qualification не меняются.

**PR пока НЕ ГОТОВ к merge.** Required gates остаются красными. Отдельный
[critical contract proposal](PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md) описывает
устаревшие classifier expectations и отсутствующий mutation anchor; это PENDING
согласования frozen criteria. Три deferred retrieval направления, gold и остальные
gates сохранены по CURRENT_WAVE_DECISIONS_RU.md. Merge/force-push/release не выполнялись.


## Исторический полный прогон: 04ff1dd; четыре migrations подтверждены

Обновление: 2026-10-08. Полный [CI 37833279436](https://github.com/Vanilla1999/DocAtlas/actions/runs/37833279436)
завершён на HEAD `04ff1dda57efb5236d7b3577d4e2736b2820df5b`, merge checkout
`1d750c0f2926ccad325f4ecb1440c623022110ec`, tree
`745fc099952eacbbe1fb5fb462e02ff0b0d0eaac`.

- Python 3.11/3.12/3.13: **8507 = 6484 PASS / 1952 FAIL / 61 ERROR / 10 SKIP**.
  Roster и outcomes одинаковы. Против 0358365 ровно **4 FAIL→PASS**: provenance,
  identity collision, policy text fidelity и exact Dartdoc. Новых/удалённых nodes,
  PASS regressions и неожиданных transitions нет.
- Из 2013 сохранивших FAIL/ERROR nodes у 47 диагностических fixture errors вместо
  IndexError теперь содержательный AssertionError; у остальных 1966 первая
  причина прежняя. Эти 47 errors **не исправлены**.
- Все 47 cases на каждой Python показывают `insufficient_evidence / docs_context /
  required_evidence_missing`, `error=None`, `source_count=0`. Видны stage counts:
  retrieved_candidates=1, query_window=1, rankings=0, qualified_fragments=0;
  projector stage пуст. Дополнительные flags и missing requirement IDs сокращены
  pytest и остаются неизвестны. Source ordering подтверждает typed block до
  projector, но не доказывает конкретную скрытую причину admission. Обход этого
  block или изменение исходных вопросов ради запуска guard tail не выполнялись.
- Advanced: **622 = 524 PASS / 98 FAIL**, полный roster/states прежние. Все девять
  независимых downstream steps выполнены и FAIL с прежними первыми причинами;
  зависимый adversarial mutation SKIP после красного baseline. Critical baseline
  **19/28 PASS**, mutants не стартовали.
- Все **6 platform SDK jobs PASS**. Main package/CLI: **77/77 PASS** на Ubuntu,
  macOS ARM и Intel. Проверены 19 actual logs, 15 SDK invocations, 30 structured/text
  lanes и 420 observations; source bindings, default/advanced cold guards,
  large/partial delivery и restart/CAS совпадают с 0358365.
- Installed scripted harness **1/1 PASS**. Release build, три wheels,
  sdist/installer и required-release **PASS**. Actual Claude Code/Codex/OpenCode
  application sessions **NOT RUN**; CLI stubs и SDK их не заменяют.
- Все 17 workflows завершились: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**.
  required-ci **113507696834 FAILURE**, P1 aggregate **113507192604 FAILURE**.

Catalog source не менялся: прежнее измерение **6918 bytes**, docs output schema
**860 bytes**. Фиксированные catalog ceilings сняты владельцем; продолжается
обоснованная минимизация без нового magic number. Output schema <1000 и отдельный
frozen retrieval criterion 800 остаются. Retrieval max **1451 pinned offline BPE
 tokens**, **24/48** within-budget cases выше 800; все 80 BPE values прежние,
80/80 canonical UTF-8 byte measurements сверены. Это не стоимость app sessions.

[Полный acceptance 04ff1dd](PR211_04FF_ACCEPTANCE.json) содержит завершённые
workflows/jobs, advanced/downstream/retrieval и installed SDK matrix.
[Core delta](PR211_04FF_CORE_ACCEPTANCE.json) содержит четыре точных transitions,
три JUnit artifact bindings и диагностические/source-order evidence.
Исторические reports ниже сохраняются; PASS не переносится на следующие commits.

**PR пока НЕ ГОТОВ к merge:** полный core/advanced и required gates красные,
actual app-client acceptance отсутствует. Следующие возможные fixture setup
migrations рассматриваются отдельно по текущему контракту. Deferred retrieval,
gold, thresholds и guards не меняются; ordinary push разрешён, merge/release/
force-push не выполнялись.

## Подготовленный следующий пакет: member/read и mtime

Следующие source changes имеют independent review, но runtime **NOT RUN** на
момент записи. Предыдущие6484 PASS и actual SDK outcomes относятся только к04ff.

- Шесть существующих module/foreign/stale-read fixtures используют настоящий
  explicit member transaction. Два прежних catalogs сохранены буквально;
  четыре README fixtures получили единственное supporting/overview membership.
  Foreign upsert использует captured CAS того же store; owned и foreign rows
  сохраняются вместе. Перед stale negatives есть реальное непустое чтение
  исходного вопроса. [Author review](PR211_MEMBER_READ_FIXTURE_REVIEW_RU.md),
  [independent review](PR211_MEMBER_READ_FIXTURE_INDEPENDENT_REVIEW_RU.md).
- Production member transaction сохраняет mtime из уже checked descriptor.
  Это устраняет отсутствующий timestamp/ложный metadata drift, сохраняя
  hash-first stale contract. Два прежних tests проверяют exact mtime, отсутствие
  drift до touch и неизменность source/generation rows после чтения. Первая
  последующая **явная** sync старой metadata либо после mtime-only touch может
  создать generation; read-path repair не добавлен. [Author review](PR211_MEMBER_MTIME_REVIEW_RU.md),
  [independent review](PR211_MEMBER_MTIME_INDEPENDENT_REVIEW_RU.md).
- Дополнительный review поймал обязательную description в двух новых catalogs;
  она исправлена до publication. Старое одобрение отозвано, corrected bytes и
  объединённые три functions в test_docs_service.py перепроверены.
  [Integration review](PR211_MEMBER_INTEGRATION_REVIEW_RU.md).

Восемь targets фактически FAIL на baseline04ff, пять modules содержат108 cases
(32 PASS/76 FAIL) и97 base names. Collection/decorators/параметры не меняются.
Отдельно проверяются ранее зелёные109 member/descriptor tests,30 trusted-storage
и2 fixture hash/CAS controls. Production metadata change не даёт оснований
переносить прежний zero-write SDK repeat PASS на новый SHA.

Self-host setup подготовлен отдельным slice: полная копия всех tracked regular
files сохраняет физические unselected distractors; membership берётся только из
неизменённого literal catalog. В copied config меняется только index.db_path на
изолированный host store. Настоящий cold public read должен подтвердить отсутствие
storage/grant; затем требуется explicit confirmed preparation с полными original
content/catalog/entry hashes и CAS None. Ошибочный cold ответ останавливает run
до подготовки и вопросов. Исходные questions, lookup_queries, scopes, positive/
negative loops и scoring/floors сохранены. Actual checkout/import origins, все
копируемые bytes и generation записываются в additive artifact provenance.
[Author review](PR211_SELF_HOST_FIXTURE_REVIEW_RU.md) и
[independent review](PR211_SELF_HOST_FIXTURE_INDEPENDENT_REVIEW_RU.md) фиксируют
точный scope; шесть новых fixture safety tests дополняют прежний roster.
Runtime нового setup **NOT RUN** на момент записи; Git witness копии — not_git,
это не проверка original storage config, Git auto-sync или actual app client.

Отдельный [critical gate contract proposal](PR211_CRITICAL_CONTRACT_PROPOSAL_RU.md)
подтверждает две причины: девять ожиданий required/forbidden относятся к retired
prose classifier, а mutation anchor отсутствует в текущем source. Предложены
проверки сохранности исходного текста/отрицаний/границ и отсутствия authority,
сохраняющие все 26 fixtures и Python grammar controls. Это **предложение для
согласования frozen criteria**, tests/gate/gold не изменены и mutants не запущены.

Deferred retrieval, frozen gold/thresholds и client requirements сохраняются.
После обычного push проверять actual GitHub CI нового HEAD; исторические
acceptance documents не являются динамическим status CI.

## Исторический полный прогон: 0358365; четыре contract-fixture migrations

Обновление: 2026-10-08. Полный [CI 37830452263](https://github.com/Vanilla1999/DocAtlas/actions/runs/37830452263)
завершён на HEAD `03583656617336a746e9192249467017d6131f29`, merge checkout
`96767d8d8499b28a701bc20055277a7362d63aa3`, tree
`b77cb4c3ed5bd60dd0ab47cd0398f1664bfd6ae1`.

- Все три Python 3.11/3.12/3.13: **8507 = 6480 PASS / 1956 FAIL /
  61 ERROR / 10 SKIP**. Против 3be9c34 ровно **24 FAIL→PASS**, ноль новых,
  удалённых, PASS→FAIL или неожиданных state transitions. Исходный focused
  791/801 не был этой полной CI-матрицей.
- Из предыдущих 25 targets прошли 24. Source-continuation fixture теперь
  действительно проходит confirmed member preparation, затем останавливается
  на `assert 'query-original' in ['query-lookup-1']`. Перенос lookup coverage на
  исходный вопрос не разрешён; этот deferred retrieval failure не скрывается.
- Промежуточный `4320a68` добавил module-size regression (1039 строк). В
  `0358365` тело fidelity test AST-exact перенесено в существующий shared helper;
  test IDs и guards прежние, модуль теперь 974 строки. Static, P2 federated и
  соответствующий core guard снова **PASS**, предел 1000 не изменён.
- Advanced: **622 = 524 PASS / 98 FAIL**, roster/states совпадают с 3be9c34 и
  4320a68. Все девять независимых downstream steps выполнены и FAIL с прежними
  первыми причинами. Critical baseline **19/28 PASS**, mutants не запускались.
- Все **6 platform SDK jobs PASS**; main package/CLI — **77/77 PASS** на каждой
  платформе. 19 actual logs подтвердили 15 SDK invocations, 30 structured/text
  lanes и 420 prepared observations. Source-binding digests и outcomes прежние.
  Release build, три wheels, sdist/installer и required-release **PASS**.
- Все 17 workflows завершились: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**.
  `required-ci` job **113497770623 FAILURE**, P1 aggregate **113498272845 FAILURE**.
  Actual Claude Code/Codex/OpenCode sessions по-прежнему **NOT RUN**.

Catalog остаётся **6918 bytes**, отдельная docs output schema **860 bytes**.
Фиксированные catalog ceilings 6144/10240 сняты владельцем; нового magic number
нет. Остальные guards, output schema <1000 и frozen retrieval criterion 800
сохраняются. Retrieval gate: maximum **1451 pinned offline BPE tokens**,
**24/48** within-budget cases выше 800; все 80 measurements прежние. Это не
фактическая стоимость в приложениях или за целую задачу.

### Следующий пакет и границы его проверки

| Slice | Сохранённое проверяемое свойство |
|---|---|
| Provenance API fixture | Точный ValueError для hidden_test_answer; убран только retired positional display budget |
| Identity collision | Разные content bindings одного stable ID отвергаются; одинаковые bindings дают валидные непустые data без edit authority |
| Policy text fidelity | Все три исходные фразы и весь text/hash/path сохраняются как untrusted source data; не выводятся policy или edit permissions |
| Exact Dartdoc fixture | Прежний class URL и отдельный robots control; настоящий pinned transport через MockTransport, те же extraction/browser guards, negatives без дополнительных requests |
| Guard setup diagnostics | 47 прежних ERROR остаются; metadata/stage counts должны показать настоящий upstream reason вместо одного IndexError |

Production, retrieval, исходные вопросы/corpora, gold, thresholds и workflows
не меняются. Collection IDs/параметры сохранены. Независимые reviews описывают
точные bytes; source-collision и provenance меняют разные nodes одного файла,
поэтому их integration проверяется отдельно по AST. Runtime следующего пакета
**NOT RUN** на момент записи: результаты 0358365 на него не переносятся.

[Полный compact acceptance 0358365](PR211_CONTRACT_FIXTURE_ACCEPTANCE.json) содержит
завершённые workflows/jobs, advanced/downstream/retrieval, actual installed SDK
matrix и границы claims. [Core delta](PR211_CONTRACT_FIXTURE_CORE_ACCEPTANCE.json)
содержит все 24 transitions, hashes и три JUnit artifacts. Исторические baseline
и оставшиеся причины ниже сохраняются. Deferred retrieval не исправлялся.

**PR пока НЕ ГОТОВ к merge:** полный core/advanced и required gates красные,
actual app-client acceptance отсутствует. Обычный push разрешён; merge,
release и force-push не выполнялись. Продолжаются только обоснованные narrow
migrations и диагностика; ошибки не переводятся в PASS заменой gold/thresholds.

## Исторический полный прогон: 3be9c34 и пакет из 25 targets

Обновление: 2026-10-08. Последний полностью выполненный main CI:
[37824782946](https://github.com/Vanilla1999/DocAtlas/actions/runs/37824782946),
HEAD `3be9c34afa49dcf4278d2910ec29ed37c305225c`, merge checkout
`fc1b4cf20e3e561a03230adcd67dd920e8464bdc`, одинаковый tree
`b27a3a70a6e3796e5e76a59395330843c7784656`.

- Core Python 3.11/3.12/3.13: на каждой **8507 = 6456 PASS / 1980 FAIL /
  61 ERROR / 10 SKIP**. Все concrete IDs и outcomes совпали. Против 40032f7
  ровно **6 FAIL→PASS** — шесть indexed MCP fixtures; новых/удалённых nodes,
  PASS regressions и иных state changes нет. Предыдущие 35 исправлений также
  сохраняются. Исторический focused 791/801 не заменяет эту полную матрицу.
- Advanced: **622 = 524 PASS / 98 FAIL**, все states прежние. Все девять
  независимых downstream steps выполнены и FAIL; adversarial mutation правильно
  SKIPPED после красного полного baseline. Required CI **FAILURE**.
- Docs contract, static, installer и installed MCP harness PASS. Все три main
  platform suites дали **77/77 PASS**, затем реальный SDK stdio PASS.
  Все три P1 stack platform SDK также PASS. Release build, wheels 3.11/3.12/3.13,
  sdist/installer и required-release PASS; release не публиковался.
- Actual SDK: 19 logs, 15 invocations, 30 structured/text prepared lanes и
  420 case observations. Все matrix outcomes, metrics и normalized source
  bindings совпадают с 40032f7. Large delivery: **39372 unique UTF-8 bytes,
  50 sources**; partial: **94 bytes**, один source и прежний missing marker.
  Это реальный MCP SDK transport и installed package evidence. Claude Code,
  Codex и OpenCode application sessions по-прежнему **NOT RUN**.
- Все 17 workflows завершились: **8 SUCCESS / 8 FAILURE / 1 SKIPPED**.
  P1 stack overall FAIL при зелёных installed SDK lanes. Green release validation
  не означает green main CI или разрешение выпуска.

Catalog **6918 bytes**, output schema **860 bytes**. Владелец снял фиксированные
catalog ceilings 6144/10240; продолжаются минимизация и измерение без нового
magic number. Output schema <1000 и остальные guards/gates не отменены.
[Актуальные решения](CURRENT_WAVE_DECISIONS_RU.md).

## Следующий пакет на публикацию и общий CI

Подготовлены отдельные reviewed slices для **25 известных baseline failures**:

| Slice | Смысл изменения | Прежние FAIL nodes |
|---|---|---:|
| Recovery diagnostics | Display cap 220 заменён точным сохранением длинного исходного вопроса; parser prohibition прежний | 3 |
| Unified MCP surface | Nullable scope с schema negatives; fidelity/no-authority guidance; реальные library examples без mode | 3 |
| Model-visible projection | Отменённый display cap и удаление missing IDs заменены full-DTO fidelity; validator/authority/confirmation/hard-stop guards сохранены | 4 |
| Source continuation | Настоящий confirmed member transaction для прежнего finite docs/jobs.md fixture; весь public read/tamper/change tail прежний | 1 |
| Installed bootstrap | Canonical/root guidance сокращён 267→249 managed words при сохранении правил; installer threshold не повышен | 8 |
| Installed lookup meaning | Две полные эквивалентные clauses сохраняют запрет переноса coverage на original question | 6 |

Все base IDs/параметры и diagnostic inventories сохранены. Новые negative controls
добавлены внутри существующих cases. Production retrieval, corpora, gold, thresholds
и workflow configuration не меняются. Из product files меняются только canonical
agent guidance и синхронный root SKILL tail. Ранние варианты compaction получили
CHANGES REQUIRED из-за literal-clause/root parity regressions; они исправлены до
публикации. Финальные review reports связаны с точными source hashes.

Runtime этого следующего пакета **NOT RUN** на момент записи checkpoint. Ни один
из 25 исправленных tests не объявляется PASS до CI следующего опубликованного SHA.
Source continuation может открыть следующую границу после исправления setup;
сравнение обязано учитывать и такой FAIL→FAIL с новой причиной.

## Подтверждённые оставшиеся причины на 3be9c34

| Gate | Первая фактическая граница |
|---|---|
| Recovery | Ожидаемый parsing origin против actual retrieval_miss; до fixture setup |
| Recovery mutation | Красный полный recovery baseline; mutants не запускались |
| Hermetic project context | 1/16 PASS, 15 FAIL по frozen query-plan/intent contract; retrieval не выполнялся |
| Legacy и V2 self-host | Legacy sync без explicit mutation; отдельный project-config/host-storage conflict также требует решения |
| Question surface | 0/100 по frozen semantic expectations |
| Agent V1 и adversarial | Setup теперь дошёл до ValueError: fixture requires a nonempty finite docs-only catalog; missing catalogs не создавались; собственные adversarial cases не достигнуты |
| Critical mutation | Baseline 28 cases: 19 PASS / 9 FAIL по normative modality; mutants не запускались |
| Retrieval evidence | **1451** tokens maximum full DTO при frozen criterion **800**; превышают **24/48** within_budget cases |

1451 — счётчик pinned offline `docatlas-offline:o200k_base`, не фактически
измеренная стоимость в приложениях Claude Code/Codex/OpenCode и не история
повторных запросов. Catalog policy не снимает этот отдельный frozen gate.

Triage core выделяет 89 mutation-grant failures, 61 setup error, 30 stale ABI
failures и 19 remote explicit-member failures. Это формы ошибок, не обещание
механических fixes: lifecycle groups включают auto-prune/vector semantics,
а ABI tests также требуют старых caps и inferred authority. У десяти admission
invariant ERROR пустой captured projection; их последующие query-need/typed_local
expectations также конфликтуют с текущим literal qualifier. Подстановка lookup
или ручных proof flags не является сохранением этих guard tests.

Это не разрешение заменить ожидания фактическими значениями, снизить thresholds,
переписать frozen gold или исправлять deferred retrieval. Исходный HEAD 21fe472d
имеет существующий красный [CI 37796983129](https://github.com/Vanilla1999/DocAtlas/actions/runs/37796983129).
Точное per-node сопоставление с ним не выполнено: JUnit artifacts отсутствуют,
а connector отклонил original core log из-за предела response body 8 MiB.
По одному job status нельзя назвать весь остаток pre-existing относительно 21fe.
Прежняя фраза «полный CI на 21fe не выполнялся» исправлена этим уточнением.

## Evidence

- [Полный compact acceptance 3be9c34](PR211_RUNTIME_FOLLOWUP_ACCEPTANCE.json):
  workflows/jobs, advanced/downstream, retrieval metrics, реальные SDK origins и
  30 ссылок на одну одинаковую нормализованную 14-case delivery matrix.
- [Core delta 3be9c34](PR211_RUNTIME_FOLLOWUP_CORE_ACCEPTANCE.json): точные шесть
  transitions, hashes и три JUnit matrices; roster восстанавливается из f0 +400 delta.
- [Core delta 40032f7](PR211_FOLLOWUP_CORE_ACCEPTANCE.json): прежние 35 transitions.
- Полный f0 baseline: [manifest](PR211_CONTINUATION_ACCEPTANCE.json),
  [roster](PR211_CONTINUATION_OUTCOMES.json.gz), [отчёт](PR211_CONTINUATION_ACCEPTANCE_RU.md).

**PR НЕ ГОТОВ к merge:** required CI и семантические gates красные, actual client
acceptance не выполнен. Обычный push разрешён; merge, release и force-push — нет.
Deferred retrieval остаётся без изменений. После публикации нужен один совместный
CI нового HEAD с полным concrete-node сравнением; PASS snapshots не наследуется.

## Историческое состояние перед f0ed956

## Текущая волна от df9b682 — review завершено, новый CI ожидается

Обновление: 2026-10-08. Работа продолжается от
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`; это следующий snapshot существующей
PR #211. Новые runtime outcomes пока **NOT RUN** и не наследуют PASS исходного CI.

Владелец явно отменил фиксированный catalog ceiling и указал стремиться к минимуму.
Прежние 6144/10240 bytes больше не являются default merge gates; нового числового
порога нет. Canonical catalog сокращён 7066→6918 bytes, output schema остаётся
860 bytes. Measurement, per-tool attribution, normal/advanced separation,
validation и source/consent/authority guards сохранены.
[Актуальное решение](CURRENT_WAVE_DECISIONS_RU.md),
[policy review](PR211_CATALOG_POLICY_REVIEW_RU.md).

Собраны отдельные reviewed slices:

- [Confirmed member transactions](PR211_MUTATION_FIXTURE_REVIEW_RU.md),
  [независимый review](PR211_MUTATION_FIXTURE_INDEPENDENT_REVIEW_RU.md) и
  [точечное обновление diagnostic inventory](PR211_MUTATION_INVENTORY_INDEPENDENT_REVIEW_RU.md).
  Сохранены 21 прежний concrete case, добавлены два integrity tests.
- [Finite code membership fixtures](PR211_MEMBERSHIP_FIXTURE_REVIEW_RU.md) и
  [независимый review](PR211_MEMBERSHIP_FIXTURE_INDEPENDENT_REVIEW_RU.md).
  Все 64 прежних test nodes и 218 assert AST сохранены.
- [Literal question boundary](PR211_QUESTION_BOUNDARY_REVIEW_RU.md) и
  [независимый review](PR211_QUESTION_BOUNDARY_INDEPENDENT_REVIEW_RU.md).
  303 прежних concrete nodes сохранены; изменены 295 cases в шести functions.
  Это producer-boundary tests, не сертификат downstream semantic sufficiency.
- [Дополнительное сокращение catalog](PR211_CATALOG_CONTINUATION_REVIEW_RU.md) и
  [независимый review](PR211_CATALOG_CONTINUATION_INDEPENDENT_REVIEW_RU.md):
  constraints и output прежние, 38 meaningful negative controls проверены review.
- [Literal source/gap fixtures](PR211_DICTIONARY_FIXTURE_REVIEW_RU.md) и
  [независимый review](PR211_DICTIONARY_FIXTURE_INDEPENDENT_REVIEW_RU.md):
  27 затронутых baseline failures, все 129 прежних nodes и 112 assert AST сохранены.

Последний полностью выполненный baseline —
[df9b682 CI 37811010878](https://github.com/Vanilla1999/DocAtlas/actions/runs/37811010878):
core на каждой Python 3.11/3.12/3.13 — 8505 cases, 6031 PASS, 2403 FAIL,
61 ERROR, 10 SKIP; advanced — 622 cases, 524 PASS, 98 FAIL.
После публикации нового snapshot обязателен полный совместный CI с concrete-node
сравнением, отдельным учётом двух новых tests и проверкой прежних PASS.

Deferred retrieval и frozen gold остаются без изменений. Остальные CI/downstream
и installed/client requirements не отменены. PR пока **НЕ ГОТОВ к merge**.
Merge, release и force-push не разрешены.

## Исторический checkpoint предыдущей волны

Дата: 2026-10-08. **PR пока НЕ ГОТОВ к merge.** Это evidence и точный остаток,
не merge/release approval. Retrieval, frozen gold, thresholds и действующие
числовые gates не изменены.

## Ветка и проверенная версия

- Начальная точка этой волны: `21fe472d983f394130849d6fd4e582043d58e9ba`.
- Рабочая ветка: `implementation/pr211-merge-readiness`, создана от PR #211.
- Все одобренные slices собраны обычным fast-forward в существующую
  `integration/stage3-v2-identity-pr1`, [PR #211](https://github.com/Vanilla1999/DocAtlas/pull/211).
- Tested source/test HEAD: `0a60111dc6de50f78f08239bd3ee9fcc3a31ad0d`.
- Фактический checkout основного CI: merge SHA `87403a079ac209641edc4b83bd08e9fd37855d46`.
- Base main: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`.
- Git tree HEAD и merge checkout идентичен: `2cdd8e5eb4c51cbd4b067e538c43e1fbe5a24023`. Конкретные run/job IDs,
  Python versions, artifact/XML hashes и правила подсчёта сохранены в
  [acceptance manifest](PR211_ACCEPTANCE.json).

Этот checkpoint и evidence публикуются отдельным documentation commit после
проверенного source/test HEAD. Source, tests и CI configuration в нём не меняются;
обычный CI запускается также на его HEAD. Самоссылочный SHA документа не требуется.
Force-push, merge, release и публикация сообщений от имени владельца не выполнялись.

## Что завершено

1. **Три исходные test migrations.** Resource examples используют unified
   library call; scope guidance проверяет сохранённый смысл и связь с нужным
   параметром; отменённый output cap ≤200 заменён fidelity-проверкой полного
   результата. Source/hash/span, missing, hard-stop и no-edit-authority guards
   сохранены. [Первый review](PR211_SLICE1_REVIEW_RU.md).
2. **Trust-resource conflict разрешён по контракту.** Root AGENTS/CLAUDE и
   другие repository files остаются `untrusted_data`; имя и scope дают
   attribution, но не instruction authority или разрешение WebFetch.
   Положительные и отрицательные controls используют реальные annotator и
   policy builder; forged caller policy не принимается.
   [Обоснование trust](PR211_TRUST_CONTRACT_REVIEW_RU.md).
3. **Catalog сокращён 7602→7066 bytes без смены лимита.** Удалены только
   логически избыточные schema конструкции и повторяющиеся пояснения. Output
   schema сохранена буквально: 860 bytes. Пять equivalence tests выполняют
   authored boundary matrix из 417 cases; проверяют прежнюю область допустимых
   inputs и отказы до service I/O.
   [Schema review](PR211_CATALOG_REVIEW_RU.md),
   [независимый review](PR211_CATALOG_INDEPENDENT_REVIEW_RU.md).
4. **Безопасный runtime выполнен.** Все пять прежних scope scenarios прошли.
   Source stdio и installed wheel/sdist проверки используют отдельные fixture
   homes и реальные MCP sessions. SDK validation-text error корректно отделён
   от обычного JSON decoding; default и advanced sessions проверяются отдельно.
   [Статический review harness](PR211_RUNTIME_REVIEW_RU.md);
   фактические runtime outcomes и job IDs — в
   [acceptance manifest](PR211_ACCEPTANCE.json).
5. **Дополнительные узкие migrations прошли review и CI.** Guidance не требует
   прежних inferred rewrites; release-resource checks проверяют public schemas
   и реальный resource getter; четыре MCP fixtures объявляют finite source
   membership и сохраняют реальные wide/narrow budget controls. Семь v4 caller
   fixtures задают явные literal content requirements и сохраняют complete
   positives, valid-partial negatives, host binding и прежние ceilings.
   [Caller follow-up](PR211_TASK_CALLER_CONTENT_WITNESS_REVIEW_RU.md),
   [независимый review](PR211_TASK_CALLER_SELECTOR_INDEPENDENT_REVIEW_RU.md).

Ни один прежний test node не удалён, не переименован, не переведён в skip/xfail
ради PASS. Старые assertions в узких slices сохранялись либо получали отдельно
обоснованный successor; семантические conflicts не подменялись actual values.
CI instrumentation добавила JUnit к существующим core/advanced commands и upload,
без изменения selectors, matrix, dependencies, timeouts, exit semantics или gates.

## Совместный acceptance

Основной [CI run 37808083737](https://github.com/Vanilla1999/DocAtlas/actions/runs/37808083737),
[release validation 37808083795](https://github.com/Vanilla1999/DocAtlas/actions/runs/37808083795).

| Проверка | Фактический результат на tested source/test HEAD |
|---|---|
| Core, Python 3.11 / 3.12 / 3.13 | **8505: 6031 PASS / 2403 FAIL / 61 ERROR / 10 SKIP**; roster и outcomes одинаковы во всех трёх versions |
| Advanced, Python 3.12 | **622: 524 PASS / 98 FAIL / 0 ERROR / 0 SKIP** |
| Пять scope variants | **5/5 PASS** |
| Source stdio / delivery module | **45 PASS** в delivery module, включая два actual source-stdio cases; эти два уже входят в 45 |
| Catalog equivalence | **5/5 PASS**, внутри них 417 authored boundary cases |
| Docs contract / static / installer | **PASS** |
| Installed platform smoke: Linux, macOS ARM, macOS Intel | **PASS** на всех трёх платформах |
| Installed-MCP harness | **PASS** |
| Required release: build, sdist/installer, wheels 3.11/3.12/3.13 | **PASS**; publish/registry/public-release jobs SKIPPED |
| Retrieval-evidence | **FAIL** на frozen 800-token criterion |
| Required CI | **FAIL** |

Числа core не суммируют три Python versions: сравниваются одинаковые конкретные
node IDs и их outcomes. В JUnit не обнаружено повторяющихся concrete node IDs; setup errors учитываются как
ERROR, существующие skips — отдельно. Десять skips: девять без local Qdrant и
один без generated story-PDF fixture. Они не добавлены этой волной.

По сравнению с первым полным CI на `b68759e`:

- Core: 5983 PASS / 2451 FAIL / 61 ERROR / 10 SKIP → 6031 PASS / 2403 FAIL / 61 ERROR / 10 SKIP; ровно **48 FAIL→PASS**.
- Advanced: 513 PASS / 109 FAIL → 524 PASS / 98 FAIL; ровно **11 FAIL→PASS**.
- Добавленных и удалённых cases нет. Переходов PASS→FAIL/ERROR/SKIP нет. Итого 59 улучшений в двух непересекающихся группах, без суммирования Python matrices.

Точный roster с outcomes сохранён в
[PR211_ACCEPTANCE_OUTCOMES.json.gz](PR211_ACCEPTANCE_OUTCOMES.json.gz), без raw
stack traces, DB/cache и user data. SHA-256 gzip и canonical JSON — в manifest;
gzip имеет mtime=0. JUnit classname с class suffix преобразуется через найденный
repository module, затем `::Class::test`, а не слепой заменой всех точек на `/`.

Прочитать сохранённый roster можно обычным Python stdlib:

```python
import gzip, json
from pathlib import Path
ledger = json.loads(gzip.decompress(Path("v2plan/PR211_ACCEPTANCE_OUTCOMES.json.gz").read_bytes()))
```

## Что подтвердил настоящий MCP delivery

Source tests используют настоящий SDK/server subprocess. Installed checks
загружают `docmancer` из site-packages вне checkout, после установки wheel;
release validation отдельно проверяет sdist и wheels трёх Python versions.

Отдельные cold sessions проверяют отказы и default preparation; после перезапуска
default server проверяются повторное чтение и CAS. Source pytest подтверждает эти
фазы и отдельный advanced positive. Полная матрица scope/module/version, partial
и large delivery выполняется в prepared advanced фазе **installed smoke**.
В обоих transport lanes — structured и text — large case сохраняет **39372 уникальных
UTF-8 bytes из 50 sources**. Partial сохраняет source и точный missing reason;
несовпадающие scope/version не возвращают source bytes. Source/library generation
rows после read checks неизменны. Числа wire payload и конкретная platform
provenance сохранены в manifest; это не model tokens и не измерение UI клиента.

Project preparation проходит через confirmed cold MCP sync. Library-version
fixtures предварительно заполнены тестом; это transport/version proof, не
сертификация network library lifecycle. SDK stdio не подменяет настоящие
Claude Code, Codex или OpenCode clients. Их доступных executables в локальном
окружении нет; реальные application/client visibility checks — **NOT RUN**.
Новые локальные dependency/model/client downloads, provider calls и обращения
к пользовательским индексам не выполнялись.

## Оставшиеся blockers

### Catalog ceiling

Действующий gate **≤6144 bytes** остаётся FAIL: **7066**, превышение **922**.
Output gate **<1000** отдельно проходит: **860**. Catalog уже содержит output
schema; эти числа нельзя складывать или переводить в обещанные model tokens.

Независимые дополнительные structural/prose passes не нашли полного сокращения
до 6144 без потери условий или изменения интерфейса. Это не доказательство
математической невозможности. Конкретное предложение для отдельного решения
владельца — **catalog ≤7168 bytes (7 KiB)**, output <1000 без изменения.
Текущий catalog оставляет 102 bytes до предложенного ceiling. **Предложение
не одобрено; число в test/gate не заменено.** Основание для необходимости
отдельного решения: пункт 3 [CURRENT_WAVE_DECISIONS_RU.md](CURRENT_WAVE_DECISIONS_RU.md).

### Полный CI и текущие contracts

Количество failures существенно больше старого focused run 791/801.
[Исторический triage b687](PR211_CORE_FAILURE_TRIAGE_RU.md) воспроизводимо
выделяет 1013 FAIL и все 61 ERROR: question planning/aliases, semantic admission,
старые ingest/sync без mutation grant, отсутствующие captured projector stages
и finite source membership. Это cohorts, не обещание простых fixes.

Для части read fixtures возможны узкие migrations на реальные member transactions
и explicit code_files с положительными source/hash/span controls. Другие tests
требуют прежних inferred policy/absence/edit semantics. Причина раннего delivery
veto в ряде projector fixtures пока не установлена по каждому seed. Остальные
failures нельзя автоматически объявлять устаревшими или pre-existing: полного
сопоставимого core CI на исходном 21fe нет.

Frozen retrieval gate по-прежнему отклоняет full model-visible DTO, превышающий
800-token ceiling по estimator этого gate. Advanced downstream recovery/mutation/project-context gates
**SKIPPED** после failure advanced pytest; JUnit upload прошёл. В связанных workflows остаются **FAIL** в P1 stack, P1 Agent Truth closure, P1.4, P1.5, P1.6, Language flow и Task 33C;
первые причины и точные run/job IDs отражены в manifest. P1.6 support mismatch
для legitimate_fact_survives_hostile_tail сам по себе не доказывает успешную
prompt injection; обязательный положительный support control не выполнен.

Original-only paraphrase, multi-section/long diversity и partial qualification/
admission остаются явно отложенными в
[RETRIEVAL_DEFERRED_ANALYSIS_RU.md](after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md).
Отсрочка не означает PASS и не разрешает исключить эти сценарии из gates.
Повышение одного catalog ceiling также не сделает весь PR зелёным.

## Исторический checkpoint 791/801

Предыдущий focused run относился к
`5310e6da83a09daa0938efa9cf68e2c0f7c99851`, не к конечному SHA этой волны и не
к полному CI. Исходный документ сохранён в
[21fe checkpoint](https://github.com/Vanilla1999/DocAtlas/blob/21fe472d983f394130849d6fd4e582043d58e9ba/v2plan/PR211_CHECKPOINT_RU.md).
Его exact 801-node roster и старые `/tmp/opencode/...` artifacts не доступны
в текущем workspace; равенство новому roster не заявляется. Новое evidence
сохранено отдельно, без суммирования пересекающихся запусков.
