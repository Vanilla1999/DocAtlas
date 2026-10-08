# PR #211: checkpoint продолжения merge-readiness

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
