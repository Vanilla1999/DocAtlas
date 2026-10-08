# PR #211: checkpoint продолжения merge-readiness

## Последний полный прогон: 3be9c34; следующий пакет test/guidance successors

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
