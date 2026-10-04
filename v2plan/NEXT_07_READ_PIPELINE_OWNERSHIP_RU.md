# 07. Grounded-first: инструкция исполнителю

Статус: **harness исправлен отдельным разрешением; неизменённый candidate REJECTED на валидной I.3; native C NOT_RUN**.
Дата решения и исполнения: 2026-10-04.
Ветка: **next07-feasibility-audit**, не main. Пользователь проводит эксперимент.
Этот документ — план выполнения, не отчёт об успешном запуске и не разрешение rollout.

## Прочитать сначала

Пользователь выбрал порядок: **сначала простой Grounded-подобный read context без
LLM; затем наши дополнительные уточнения, по одному**. Не возвращаться к поиску
универсального event-condition parser перед выдачей документации.

Предыдущая попытка 07.1 завершена BLOCKED и НЕ переименована в PASS.
Полный прежний план сохранён без изменения bytes в
[NEXT_07_SCOPE_TRIAL_HISTORY_20261004_RU.md](NEXT_07_SCOPE_TRIAL_HISTORY_20261004_RU.md).
Его старые команды «следующее действие» — история, не параллельная очередь работ.
[Feasibility evidence](artifacts/next07/feasibility-audit-20261004.json) не менять.

### Карточка запуска для coding-агента

1. Прочитать `v2plan/AGENTS.md` и этот план. Выполнять I.0 → I.6 по порядку.
2. Сейчас разрешён только текущий шаг; не писать код последующих слоёв заранее.
3. До patch записать: шаг, заменяемую обязанность, allowed files и проверку.
4. Выполнить проверку, сохранить исходные outputs и verdict шага.
5. При DONE шага перейти к следующему. При REJECTED/BLOCKED закончить попытку.
6. В конце обязательно выдать итог по шаблону ниже, даже при ранней остановке.

**Не начинать с полного pytest, новой модели, compiler, словаря, удаления gates
или переписывания failing tests. Начать с baseline и настоящего Grounded run.**

## 1. Что именно проверяем

Гипотеза: часть полезных фактов теряется не в поиске, а при попытке доказать
соответствие каждого короткого окна вопросу. Проверяем замену read-маршрута:

```text
проверенный исходный corpus и scope
  → структурные source-bound passages
  → один FTS5/BM25 порядок
  → целые цитируемые окна
  → упаковка в 800 / 3
  → final source/span/budget checks
  → retrieval_only context
```

Не обещаем полный или безошибочный ответ. Не обещаем, что Grounded всегда лучше.
Grounded здесь — поставщик контекста, а не генерирующая ответы LLM.
Для LeaseClient в этой попытке нужен конкретный результат: оба исходных факта
видны в возвращённом packet, а не только в hits, snapshot или read_next.

### 1.1. Четыре независимые обязанности

| Обязанность | Правило candidate |
|---|---|
| Безопасность и происхождение | Проверяются всегда; никакая relevance оценка не даёт исключений |
| Полезность для чтения | Grounded-подобный lexical order; это предложение материала, не proof |
| Применимость утверждения | Неизвестная остаётся неизвестной; нет автоматического support credit |
| Полнота ответа | Не является условием выдачи полезного частичного контекста |

### 1.2. Явное изменение read-policy в этом эксперименте

В isolated candidate отсутствие semantic/applicability proof само по себе НЕ
является причиной запрета исходного материала. `3 terms + adjacent pair` и
проверка всех constrained needs против каждого body больше не определяют
право обычного read-окна участвовать в selection. Не менять 3 на 2.

Это изменение политики, а не behavior-preserving refactor. Оно не означает
`unknown = applicable`, не переносит condition exception на default и не
разрешает утверждать факт о production/environment, не названном источником.
Не присваивать routing IDs, lexical score или BM25 статус смыслового witness.

Подтверждённое несоответствие source/identity/scope/version и существующий
надёжно установленный explicit condition mismatch не разрешаются. Отсутствие
frame, отсутствие condition в source и установленное противоречие — разные
ситуации. Нельзя назвать любой False старой `_applicable_context` противоречием:
она также возвращает False для unsupported. Не создавать новый semantic
classifier для противоречий в этой попытке; использовать только уже проверяемое
основание, а непредставленные случаи оставлять unknown.

### 1.3. Неизменные границы

- 800 **whole-DTO admission tokens** через existing `docs_context_budget_tokens`;
  максимум 3 source rows. Tokenizer count и bytes/4 дополнительно, не вместо него.
- Source/security/project identity/module scope/version/freshness/lifecycle/
  snapshot/hash/span/request/exact guards. Сохранять их реальные параметры.
- Условия, отрицания и source subject сохраняются с цитатой. Не отдавать число
  или имя exception отдельно от ограничивающего текста.
- Нет новых моделей, embeddings, natural-language parser, aliases, tuning,
  library-specific правил, guessed answer values или дополнительных lookup.
- Не расширять existing candidate/hydration/source/call caps. Pinned профиль
  структурного разбиения — объявленная переменная research-индекса, не изменение
  всех production budgets. Все внутренние caps записать в I.0; при их превышении
  фиксировать omission, не поднимать предел.
- Не изменять production/defaults/main, public schema и release policy.
- Не считать false proof/edit flags или Markdown boundaries доказательством
  сохранения всех смысловых ограничений. Нужны source checks и negative controls.

### 1.4. Старые tests: не прятать смену политики

До candidate создать `policy-delta.json`: exact node ID, старое обязательство,
новое ожидаемое поведение, причина, остающиеся защиты. Получить node IDs через
pytest collection, не угадывать parametrized ID.

Разрешённая смысловая разница — read context может появиться при unknown
applicability или без three-term/pair witness, не получая proof/coverage/edit.
У `tests/docs/test_read_context_admission_boundary.py` отдельно разобрать
condition-параметр `test_added_identity_or_condition_does_not_preserve_context`
и lexical-only параметры `test_local_topic_witness_rejects_heading_echo_and_scattered_terms`.
Параметр с чужой exact identity и реальные security/source negatives НЕ мигрируют
вместе с соседними policy-параметрами. Не разрешать heading-only/echo механически
только потому, что тест находится в той же функции.

В этом эксперименте старые tests и frozen labels НЕ редактировать. Добавить
новые candidate controls отдельно и запускать старые тоже. До кода зафиксировать
конечный allowlist только намеренных policy-различий; после результатов не
расширять его. Непредусмотренные failures — REJECTED.

80-case frozen suite остаётся отдельным неизменным acceptance, включая прежние
expected-empty negatives. Появившийся там packet может оказаться policy-конфликтом,
а не утечкой или ложным ответом: описать его правильно, но не засчитать PASS и
не менять gold. Требуется новое продуктовое решение вне этой попытки.
Native acceptance не равна зелёному required CI; нерешённая миграция старых checks
и блокеры 06 остаются блокерами rollout.

## 2. Что брать из Grounded

**Reference:** `@arabold/docs-mcp-server@3.2.1`, source tag `v3.2.1`, commit
`f2938c47bb8937c650f0d5ddb614f867773b29f4`.
Не заменять pin на latest. Проверить версию установленного package, lock,
registry integrity и source ref; записать результат. Название версии само по
себе не доказывает равенство локальных bytes опубликованному package.

Проверенные первичные файлы на этом commit:

- [MarkdownPipeline](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/scraper/pipelines/MarkdownPipeline.ts)
- [GreedySplitter](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/splitter/GreedySplitter.ts)
- [DocumentStore: query construction и FTS-only ranking](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/DocumentStore.ts)
- [FTS schema](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/db/migrations/009-add-pages-table.sql)
- [SearchTool](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/tools/SearchTool.ts)
- [Assembly](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/src/store/assembly/strategies/MarkdownAssemblyStrategy.ts)
- [MIT license](https://github.com/arabold/docs-mcp-server/blob/f2938c47bb8937c650f0d5ddb614f867773b29f4/LICENSE)

Заимствовать можно чистые части: FTS escaping, SQL ranking, greedy structural
packing. Для кода сохранять `Copyright (c) 2025 Andre Rabold`, MIT notice,
upstream path/ref/blob SHA и diff адаптаций в `v2plan/third_party/grounded-3.2.1/`.
Не копировать чужие credentials/config/store и весь server stack в production.

Grounded может нормализовать Markdown через HTML. Его rendered content НЕ
автоматически точные bytes исходного файла. Для DocAtlas нужен sidecar с
original source identity и offsets; при неоднозначном mapping — отказ от окна.
Запрещено сочинять spans, искать похожую цитату в другом месте или незаметно
подставлять весь parent. Совпадение document ID не доказывает span mapping.

**Важно:** предыдущий ответ в чате про LeaseClient был реконструкцией FTS,
не packaged Grounded run и не ответом LLM-reader. Ранг `error/overview/default`
не ожидаемый результат теста. В этой попытке установить реальные outputs.
Сохранённый `M2_GROUNDED_MECHANISM_CHECK_RU.md` касается mkdocs-05, не LeaseClient.

## 3. Три разных результата, не смешивать

| Имя | Что исполняется | Что можно заявить |
|---|---|---|
| N — native baseline | Текущая ветка через existing public-call harness | Нынешний возвращённый packet |
| G — upstream reference | Настоящий pinned npm CLI/MCP Grounded, FTS-only | Реальная выдача Grounded; не parity с бюджетом DocAtlas |
| C — Grounded-like candidate | Source-bound адаптация, наши guards, public path и 800/3 | Только измеренный candidate result |

G search limit=3 ограничивает initial hits, не полный размер вывода. G нельзя
назвать прошедшим 800/3 без измерения. Его не обрезать вручную для удобного PASS.
SQL replay и прямой вызов Python helper остаются diagnostics, не G или C native.
Ответ reader-модели в эту model-free попытку не входит; не писать его от её имени.

# Часть I. Минимальная основа без LLM и наших relevance-уточнений

## I.0. Заморозить входы и исполнение

**Изменяемая ответственность:** нет; только protocol/capture.
**Allowed:** research runner/tests, новые artifacts, журнал этого плана.

Проверить checkout. Не делать reset/stash/clean и не переключать грязный checkout.

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Runtime anchor до этого docs-only плана: `4dac4d7dbbca55beb400dc6503ab54872f766f01`.
Зафиксировать реальный стартовый HEAD, полный tracked binary diff и hashes
untracked inputs. Сохранить копию baseline для парной проверки; HEAD без dirty
patch не считается тем же baseline. Работать в isolated checkout/process.

Новый output: `v2plan/artifacts/next07/grounded-first/<run-id>/`, exclusive create.
Временные DB/package installation — снаружи repo. Сохранить protocol с question,
source hashes, package/config/interpreter versions, caps, candidate algorithm,
allowlist policy-delta и всеми criteria ДО реализации C.

Проверить `.venv/bin/python`; если отсутствует, выбрать один имеющийся проектный
интерпретатор и записать его. Не считать shell Python эквивалентом project env.
Сеть допустима для отдельной установки pinned package. Сам benchmark — только
локальный frozen corpus, без внешних запросов, API keys, embeddings и telemetry.
Не ослаблять изоляцию при ошибке установки; BLOCKED_ENV.

**DONE I.0:** provenance/protocol/policy-delta созданы; inputs доступны; baseline
не затронут. Отсутствующий полный архив 49 claims отметить сейчас, не в конце.

## I.1. Реальный Grounded на исходном LeaseClient

**Изменяемая ответственность:** нет; comparator.
**Allowed:** `v2plan/next07_grounded_reference.py`, `v2plan/test_next07_grounded_first.py`,
новые artifacts и third-party notices. Runtime DocAtlas не менять.

Взять точные fixtures из `tests/docs/test_need_local_admission.py`, не переписать
их в более удобный язык. Обязательны оба параметра `(17, LeaseExpired)` и
`(29, WaitExpired)`. Question неизменён:

```text
What is LeaseClient default timeout duration for requests and which exception is raised when an operation expires?
```

Три отдельных исходных файла, включая overview:

```text
default.md:  # LeaseClient\n\nThe default timeout is 17 seconds.\n
error.md:    # LeaseClient\n\nAn expired operation raises `LeaseExpired`.\n
overview.md: # Overview\n\nLeaseClient default timeout duration requests exception operation behavior documentation.\n
```

Строки выше обозначают bytes с `\n`, а не буквальные backslash в файле.
Второй параметр меняет только исходные value/error согласно existing test.

Отдельные свежие stores для двух параметров; никакого corpus с обоими ответами
в одном индексе. Все три файла — одна library/version. Не индексировать только
полезные файлы, не удалять overview, не подсказывать answer в query/title.

Использовать installation/config шаблон из
`roadmap/search-quality-2026-10-01/m2_grounded_mechanism_probe.py`, но НЕ запускать
его mkdocs-main как LeaseClient experiment. Создать узкий runner для этих inputs.
Проверить реальные CLI flags через `--help`. После установки типовой вызов:

```bash
node "$ENTRY" scrape lease-fixture "$FILE_URI" --max-pages 1 --max-depth 1 --no-clean --config "$CONFIG" --store-path "$STORE" --no-telemetry --no-logo
node "$ENTRY" search lease-fixture "$QUESTION" --limit 3 --output json --config "$CONFIG" --store-path "$STORE" --no-telemetry --no-logo
```

Scrape вызвать по одному разу для каждого из трёх файлов; file-access разрешён
только для fixture-root, symlinks выключены. Записать stdout/stderr/exit code,
реальные chunks, порядок results, citations, размеры и zero-embedding check.
CLI использует SearchTool, но не выдавать CLI capture за новый MCP transport run.

Тем же corpus получить N через existing `capture_fixture`/`capture_public_call`.
Если reused capture не соответствует source/config/runtime hashes, сделать fresh.

**DONE I.1:** реальный G содержит оба факта с заголовком/условием для обоих
параметров; N и G сохранены. Успех G ещё не C recovery.
**REJECTED:** валидный G не доставляет обязательный факт — сохранить реальный
контрпример, не менять запрос/limit/chunks и не переходить к копированию как к
доказанному решению. **BLOCKED:** package/run недоступен. SQL-подмена не разрешена.

## I.2. Source-bound retrieval: одна замена, пока без нового admission

**Заменяем:** формирование initial read-candidates, не proof/selector.
**Allowed:** `v2plan/next07_grounded_candidate.py`, разрешённые pure ports в
`v2plan/third_party/grounded-3.2.1/`, candidate tests и artifacts.

Строить отдельный research FTS index только из проверенного current corpus,
с теми же source identities/scope/version. Не запускать поиск по outputs старого
projector: он уже мог удалить default/error. Для native integration inventory
брать на границе `query_project_docs` до qualification/rerank, не финальный context_pack.

Зафиксированный начальный алгоритм C:

1. Структурные Markdown units с original offsets. Greedy границы по pinned
   Grounded: min 500 / preferred 1500 / hard max 5000 символов. Это structural
   профиль, не token budget. Сохранять original bytes и heading ownership;
   не требовать нового natural-language parser. Превышающие существующий resource
   cap units отмечать omitted, не увеличивать cap и не делать parent rescue.
2. Query construction — pinned full phrase OR escaped terms; tokenizer
   `porter unicode61`; BM25 weights `(10.0, 1.0, 5.0, 1.0)` для content/title/url/path.
   Никаких stopword/alias additions под кейс. Не менять weights после results.
3. Один order, без component/need/facet boosts и query rewrites. Initial pool —
   не больше 20 и не больше меньшего existing cap из I.0. Tie-break: canonical
   source identity, original start/end; не answer values и не fixture names.
4. Привязать proposals к current snapshot и точным original spans. Internal row:
   source key, snapshot hash, start/end, original text, owner/dependency spans,
   retrieval order. IDs и score служат адресации/порядку, не approval.

Предпочтительно переиспользовать existing structural/span utilities. Если нужен
порт upstream splitter, сохранять лицензию и явно показать differences: original
byte preservation вместо upstream normalized Markdown. Python-port не называть
native Grounded. Проверить query/ranking parity с G на одинаковых индексных
строках; отличия разбиения фиксировать отдельно, не скрывать «почти parity».

Нельзя из span-unavailable сделать полный raw document как запасной результат.
Короткий документ допустим целиком, если он с самого начала один индексный unit.
Нельзя вручную конструировать default/error proposals из ожидаемого ответа.

**DONE I.2:** source-bound proposals воспроизводимы; в LeaseClient оба факта
присутствуют; bytes/offsets и лимиты проверены. Downstream N пока может отказать —
это не провал isolated retrieval stage и не recovery. Ошибочный span — REJECTED.

## I.3. Read decision: заменить semantic permission, не безопасность

**Заменяем:** competing read-permission decisions, не retrieval order/packing.
**Allowed:** research candidate adapter и tests. Для isolated runtime patch:
`docmancer/docs/application/read_context_admission.py` и
`docmancer/docs/application/need_context_disposition.py` — только read responsibility.
Не импортировать v2plan из production modules; research runner устанавливает
scoped replacements, восстанавливая их при выходе.

Один owner проверяет конкретные proposals I.2: source guards, exact/subject,
current request/snapshot/span и видимость известных зависимостей. Переиспользовать
existing `prepare_source_probe`/reference binding, не подделывать qualified flags.

Не использовать `qualify_evidence` reason whitelist, compiler success, all-needs
condition loop и three-term/pair floor как повторное read permission.
Proof consumers вне read-candidate остаются неизменными. Старое mixed False
не превращается в известный mismatch; known mismatch требует своего проверяемого
основания. Unsupported остаётся unknown, а не supported.

Окно включает subject/owner и известные ограничивающие dependencies. Structural
closure проверяет только распознаваемые связи; отсутствие edge не доказывает
отсутствие условия. Поэтому проверяются отдельные trailing/cross-paragraph
controls из §4. Если их сохранность не обеспечена — REJECTED, не новый regex.

**DONE I.3:** обязательные короткие source-bound positives разрешены как context;
source/exact/mismatch/clipping controls запрещены; ни один факт не получил
нового applicability/support/coverage/edit credit.

## I.4. Packing и native wiring: одна selection-замена

**Заменяем:** отбор read packet, включая empty-only доступ generic proposals.
**Allowed:** research runner/candidate/tests. Из runtime только wiring в
`_project_docs_service_part03.py`, `_project_context_service_part01.py`,
`need_context_projection.py`, `_docs_context_projection_core.py`,
`docs_context_projection.py` внутри `docmancer/docs/application/`.
Изменять их не все сразу: отдельный wiring patch на границу, без новой ranking
policy. `project_doc_ranking.py` можно менять только для проведения уже checked
read-proposals без требования qualified IDs; его proof/legacy поведение не менять.

Это opt-in isolated candidate, не новая production/default OR fallback.
Источник не может включить candidate метаданными. Existing N запускается
отдельно на идентичном corpus, не как скрытый fallback C.

Зафиксированный packer C — **first-fit по единственному order I.2**:

1. Перебирать уже source-checked предложения; только точные duplicate/contained
   spans той же identity/snapshot убрать. Не объединять разные версии/документы.
2. Предлагать целое original окно вместе с обязательными owner/dependencies.
   Нет budget-driven clipping предложения, summarization и поиска answer substring.
   Несмежные spans не выдавать за одну непрерывную цитату с выдуманными lines.
3. Вычислить стоимость полного serialized DTO с metadata. Если окно не помещается
   или превышает 3 source rows, записать omission и перейти к следующему.
   Не сокращать уже принятые факты, не поднимать budget.
4. Пересчитать source/span checks на final bytes. Пустой результат честно
   insufficient, не «ответа в документации нет».

First-fit выбран как простой фиксированный comparator, НЕ как оптимальный
packer. Утрата прежних фактов из-за этой простоты — измеримый результат, а не
повод добавлять в ту же попытку knapsack, novelty thresholds или rescue.

Native C должен пройти реальный `get_docs_context`/MCP handler и existing
`validate_model_visible_projection`, а не только experimental renderer.
Prefit/rerank обязаны передать этот же законный inventory; не ставить exemptions
всем hit IDs. Трассировать actual calls, включая facade динамические hooks.

В C не выполнять старые secondary relevance/selection passes поверх нового
order. В частности, `select_joint_context`, `select_query_block_context` и
`select_query_block_recovery` не должны незаметно менять C packet. Их ordering/
exploratory функции выключаются только в isolated selection arm, не глобально.
Source binding, serialization, validation и capability/security checks НЕ
выключать вместе с ними. Обычный N остаётся неизменным.

Сохранять для N/C: prefit input/output, rerank output, proposed/selected windows,
core output, output после facade, payload непосредственно перед возвратом MCP.
Наличие факта в `read_next`/snapshot не считается доставкой в sources.

**DONE I.4:** оба native параметра доставлены в final C, цитаты и ограничения
верны, DTO валиден и <=800/3. Это пока target-local success, не общий acceptance.
Если для проводки понадобилась новая обязанность вне списка — BLOCKED, не
редактировать другие слои без границы. Если meaningful C не прошёл — REJECTED.

## I.5. Одна парная приёмка, без подбора кандидата

**Allowed:** runner/tests, новый artifacts directory. Algorithm заморожен.
Переиспользовать `load_protocol`, `documents_for`, `isolated_service`,
`index_project`, `capture_public_call`/`observe_call`, `assess_context`,
`audit_payload`. Не писать новый evaluator и не вызывать старый rejected
`selection_direction_ablation.candidate_function()`.

Сначала обязательные controls §4. Затем один paired N/C replay всех 80 frozen
cases с одинаковыми исходными bytes/config и честной разницей retrieval profiles.
Corpus split/grouping и BM25 statistics записать; не сравнивать scores разных
индексов как одну шкалу. Исторические чужие runs не подменяют fresh N.

Сохранить множества `(case_id, claim_id)`, не только сумму:

```python
lost = baseline_supported_ids - candidate_supported_ids
gained = candidate_supported_ids - baseline_supported_ids
assert not lost
```

Отдельно сохранить все ранее подтверждённые 49 claim IDs из versioned evidence
и полезные partial facts. Если доступна лишь сумма 49 без списка/provenance,
историческая retention остаётся BLOCKED; не восстанавливать IDs догадкой.
Fresh baseline уже потерял прежний факт — отдельный blocker, не новая норма.
`needs_review` не автоматически PASS и не автоматически ложное утверждение.

Старые expected-empty frozen negatives не менять. При новом packet указать,
это source violation, false assertion, irrelevant context или конфликт старой
abstention policy; по текущему frozen acceptance всё равно не PASS.

Focused tests запускать project interpreter, сохранив exit code/log/JUnit:

```bash
DOCATLAS_OFFLINE=1 "$PY" -m pytest -q \
  tests/docs/test_need_local_admission.py \
  tests/docs/test_read_context_admission_boundary.py \
  tests/docs/test_admission_guard_composition.py \
  tests/docs/test_source_window_eligibility.py \
  tests/docs/test_requested_evidence_retention.py \
  tests/docs/test_shared_context_proposals.py \
  tests/docs/test_evidence_set_context_delivery.py \
  tests/docs/test_evidence_set_delivery_acceptance.py \
  v2plan/test_next07_grounded_first.py \
  --junitxml="$OUT/focused.xml"
```

`$PY` и `$OUT` фиксируются в I.0. Новый test module создаётся этим экспериментом;
команда не утверждает, что он уже существует. Candidate должен быть установлен
в том же pytest process; завершившийся monkeypatch script не влияет на новый
процесс. Проверить импортированные function origins/hashes перед run.
Manifest новых tests обновлять по существующим правилам, не relabel старые nodes.

Только после successful controls/retention — один парный full offline run N/C:

```bash
DOCATLAS_OFFLINE=1 "$PY" -m pytest tests/ -m 'not live and not live_network' -q --junitxml="$OUT/full.xml"
```

N и C имеют разные OUT. Required gates/stdio/schema/footprint/quality-lineage/
mutation commands брать из pinned workflows/scripts и записать в I.0, не
изобретать флаги. Блокеры плана 06 не чинить и не прятать в этом trial.
Unseen validation не выполнена этим exposed replay; не заявлять обобщение.

## I.6. Конечный verdict части I

| Verdict | Заранее заданное условие |
|---|---|
| **DONE / VALIDATED_LOCAL** | Есть настоящий G; native C доставляет оба LeaseClient параметра и partial positive; не теряет fresh baseline и исторические 49 IDs/partial facts; source/condition/clipping negatives соблюдены; frozen negatives без новых forbidden packets; DTO <=800/3; нет непредусмотренных failing nodes; удалена названная read-ответственность, а не добавлен fallback |
| **REJECTED** | Валидный candidate нарушил хотя бы один обязательный positive/negative, потерял факт, превысил лимит, подменил source/span, добавил неподтверждённый credit либо потребовал case/tuning/rescue для PASS |
| **BLOCKED** | Не хватает исполняемой среды/pin/corpus/provenance/исторических IDs; невозможно проверить mapping или требуемый caller вне allowed scope; обязательная проверка не запускалась. Это отсутствие достаточной проверки, не доказательство невозможности метода |

Давать отдельные статусы G, source mapping, C native, retention, regression,
held-out. Не прятать valid failure под BLOCKED_ENV другого этапа.
DONE здесь — локальная приёмка конкретного candidate, не READY/rollout.
Предсуществующие 06 failures и обязательность CI остаются открытыми.

# 4. Обязательные positives/negatives для C

Fixtures и expected outcomes заморозить в I.0. Не использовать их значения
в runtime. Существующие tests остаются; новые controls не заменяют их.

| ID | Input | Обязательный outcome |
|---|---|---|
| P1/P2 | Исходные separate default/error + overview, оба параметра | Оба факта в final sources, правильный owner и expiration сохранены |
| P3 | Тот же root, default есть, error отсутствует | Default доставлен; exception не выдумана; нет full support |
| P4 | Неподдержанная грамматическая формулировка, тот же источник | Parser failure сам по себе не создаёт empty; exact constraints не ослаблены |
| P5 | Неизвестный scope `only for administrators`, безусловный source | Допустим исходный context без утверждения admin applicability; unknown не получает credit; это заявленная policy delta |
| N1 | Чужой project/module/subject/owner либо exact/version mismatch | Чужой факт не доставлен через C |
| N2 | Stale/archived при current intent, dirty index, unsafe/injection | Существующие source guards запрещают повреждённый вариант |
| N3 | Mutation request/snapshot/hash/path/document ID/start/end | Final validator запрещает источник, не чинит metadata нормализацией |
| N4 | Поддержанная форма: requested disabled, source явно enabled | Не выдать enabled как подходящий disabled fact; existing known-mismatch expectation сохраняется |
| N5 | `When X happens, A does not raise E.` | Не доставить positive `A raises E`; отрицание остаётся в исходной цитате |
| N6 | `A raises E. Only when X happens.` и вариант с restriction в следующем абзаце | Если факт доставлен, соответствующая restriction тоже видна; нельзя выдавать clipped версию как целую |
| N7 | Subject/condition только в owner/introduction; удалённая dependency | Нет допуска по скрытой dependency; нужен видимый bound source context |
| N8 | Тот же ответный токен в чужом subject/source рядом с правильными keywords | Token overlap не выполняет P1/P2 и не чинит identity |
| N9 | Очень маленький packet budget и oversized целый unit | Нет clipping/rescue; честный omission/insufficient, guards не переиспользованы |
| N10 | Heading-only, question echo, рассыпанные keywords | Не засчитывать как factual recovery; запрещённые старым контрактом outputs отдельно в policy ledger, не прятать под общим PASS |

Для negative-control сначала подтвердить рабочий positive, затем менять один
фактор. Пустой pipeline не доказывает работу guard. Правильный факт может
соседствовать с лишним overview: это не делает delivery ложной, но трату бюджета
и irrelevant material учитывать отдельно. Не требовать заранее конкретный rank.

# Часть II. Наши уточнения — только поверх сохранённого простого baseline

**Не запускать до DONE I.6. Не использовать для исправления REJECTED части I.**
Если I завершена REJECTED/BLOCKED, сохранить результат и закончить; следующий
эксперимент требует отдельного решения, а не автоматического расширения правил.

Сохранить C0 как неизменный baseline. Уточнения не обязательны: при отсутствии
конкретного пробела завершить II как `DONE / NO_CHANGE`, без искусственной правки.

## II.1. Existing source continuation, без вытеснения цитат

Проверить, доступны ли уже существующие bounded `read_next`/source continuation
для недоставленного материала. Если да — no-op с evidence. Иначе подключить
только existing механизм к C0. Не писать новый recovery engine и не расширять
источники, scope, budgets или tool permissions.

**Allowed:** wiring `docs_context_projection.py`; existing `source_continuation.py`
только подключение, не security/lifecycle/capability logic; related tests.
**Заменяемая обязанность:** подключение существующего read-next к новому packer,
не новая relevance policy. Отдельный patch, не вместе с II.2.

**DONE:** все C0 sources/facts/conditions сохранены; metadata помещается в те же
800; capability/source guards прежние; существующий reader получает правильный
непрочитанный range. Если metadata не помещается — не вытеснять факт ради неё.
Новый retrieval/search/fallback или потеря C0 факта — REJECTED уточнения, вернуть
C0 в isolated run, сохранив failed result. C0 этим не объявляется плохим.

## II.2. Existing focused lookup workflow

Проверить действующую инструкцию из NEXT_03 и `_docs_server_tool_data.py` /
`_docs_server_resources.py`. Она должна сохранять исходный вопрос, subject,
environment, conditions, negation и известные sourced facts между вызовами;
no progress → partial/unknown, без повторов и расширения call limits.

Использовать существующие `lookup_gap_probe.py` и tests, четыре сценария
both/partial/absent/wrong. Native root-only и assisted lookup результаты хранить
отдельно. Модель для генерации lookup не добавлять. Ручной lookup не доказывает
улучшение поведения реального агента и не заменяет P1/P2.

**Allowed:** только существующие instruction fields и related tests, если найдён
реальный пробел; retrieval/admission/selector не менять.
**DONE:** действующий workflow согласован и bounded follow-up controls прошли,
или доказан NO_CHANGE. Missing value остаётся unknown, wrong source не появляется,
flags и budgets прежние. Нужен новый semantic parser/LLM/ranking — STOP вне scope.

После II.2 завершить работу. Не восстанавливать старые all-needs/three-term veto
под названием «уточнение». Facet boosts, compound coverage optimizer, новая
compression policy и LLM-reranker — не автоматические следующие стадии.

## 5. Allowed files и запись результатов

Research additions этой попытки:

```text
v2plan/next07_grounded_reference.py
v2plan/next07_grounded_candidate.py
v2plan/next07_grounded_run.py
v2plan/test_next07_grounded_first.py
v2plan/third_party/grounded-3.2.1/NOTICE.md
v2plan/third_party/grounded-3.2.1/LICENSE
v2plan/third_party/grounded-3.2.1/manifest.json
v2plan/third_party/grounded-3.2.1/fts_query.py
v2plan/third_party/grounded-3.2.1/passage_splitter.py
v2plan/artifacts/next07/grounded-first/<run-id>/
```

Создавать только нужные файлы. Pure ports не нужны при прямом reuse upstream.
Не складывать npm/node_modules/DB в git. Runtime allowed files заданы по стадиям
выше: это не разрешение менять их одновременно. Остальные runtime, parser,
schema, frozen labels, historical reports и unrelated dirty files неизменны.

Minimum artifacts: `protocol.json`, `provenance.json`, `policy-delta.json`,
source/package/code manifests, G raw stdout/stderr, N/C public packets,
snapshots, stage traces, final validator errors, paired claim IDs, lost/gained/
partial tables, commands/exit codes/JUnit, `SUMMARY_RU.md`.
Большой архив допустим с durable location+hash; один локальный `/tmp` не итоговая
доказательная база. Secrets не коммитить. Original failures не перезаписывать.

### Финальный ответ исполнителя

```text
Branch / baseline HEAD+patch / candidate HEAD+patch:
Последний выполненный шаг:
G actual package run: DONE | REJECTED | BLOCKED
C final packet: DONE | REJECTED | BLOCKED | NOT_RUN
Часть I verdict: DONE | REJECTED | BLOCKED
Часть II: DONE | NO_CHANGE | REJECTED | NOT_RUN
LeaseClient P1/P2/P3: фактически доставленные source snippets + conditions
Recovered / lost / retained partial fact IDs:
Hard guard / budget / span violations:
Policy conflicts и старые failing nodes, не скрытые из отчёта:
Unseen / reader evaluation: NOT_RUN, если не выполнены отдельно
Изменённая и удалённая ответственность:
Changed files / exact commands / artifacts:
Not_run и причина:
Один следующий шаг или «эксперимент завершён, rollout не разрешён»:
```

## 6. Статус на момент записи этого плана

Все I.0–I.6 и II.1–II.2: **NOT_RUN**. Создан только план и согласован маршрут.
Код, guards, fixtures, budgets и старое evidence этой записью не изменены.
Предыдущие 2 diagnostic PASS и 07.1 BLOCKED — исторический результат, не новая
приёмка. Успех Grounded на LeaseClient, native recovery и сохранение 49 facts
предстоит измерить; они не выводятся из этого документа.

## 7. Журнал исполнения 2026-10-04 — BLOCKED

Baseline: `1b1cf6b7` + исходный dirty patch, ветка `next07-feasibility-audit`.
Evidence: [SUMMARY_RU.md](artifacts/next07/grounded-first/20261004-1b1cf6b7/SUMMARY_RU.md).
Runtime/defaults и чужие dirty files не изменены; прежняя compiler-only попытка
не возобновлялась. Historical BLOCKED остаётся отдельным результатом.

| Шаг | Измеренный результат |
|---|---|
| I.0 | Baseline archive/patch/hashes, isolated checkout, protocol, collected policy allowlist и 49 historical IDs сохранены. Полная предварительная заморозка конкретных новых controls не завершена: это ограничение исполнения, не полный DONE I.0. |
| I.1 | G actual package run DONE: оба факта и owner/expiration видны для обоих параметров. Fresh N captures сохранены. Package integrity, installed/tarball bytes и upstream tag/SHA проверены. |
| I.2 | Isolated retrieval diagnostics: 8 PASS; оба факта в original spans; same-index-row BM25/rank parity. Current-source native integration не проверена; полный source-bound DONE не заявляется. |
| I.3 | BLOCKED: harness передал index DTO `project_file` вместо подготовленного read DTO `project_doc`; обязательный рабочий positive не получен. |
| I.4–I.6 | NOT_RUN: переход запрещён без корректной проверки I.3. Итог части I — BLOCKED, не recovery. |
| II.1–II.2 | NOT_RUN: DONE части I отсутствует. |

Первый I.3 run invalid: logger использовал `__dict__` для slots dataclass.
Единственный разрешённый повтор исправил только logging через `asdict`:
**9 PASS / 15 FAIL**, но positive остановлен с `missing_project_request` до
read-policy. Twelve mutation tests остановились на своих positive preconditions;
restriction test отказал пустым pipeline и **не доказывает сохранность restriction**.
Это не valid algorithm rejection и не успешная guard acceptance. Второго
исправления harness, подмены source_class, расширения candidate или rescue нет.

Новые control fixtures были конкретизированы после I.0, а I.2 proposals ещё не
имели доказанной native source eligibility. Поэтому порядок предварительной
заморозки/переходов выполнен не полностью. Эти diagnostics не повышаются до
acceptance; это дополнительное основание не заявлять VALIDATED_LOCAL.

G: реальный CLI SearchTool, **не новый MCP transport**; нормализованный текст не
аттестован как original spans. N final sources содержат overview; бюджет 313/314
whole-DTO admission tokens. C final packet, retention 49 IDs/partial facts,
frozen replay, old-policy regression, required gates, full suite и unseen/reader
evaluation NOT_RUN. Никакая часть плана 06 не закрыта этим исполнением.

Один следующий шаг, только новым решением: исправить research DTO-boundary и
завершить предварительную заморозку controls до новой попытки. Использовать
existing authenticated conversion, не переписывать source_class и не ослаблять
guard. Текущая попытка завершена; rollout не разрешён.

## 8. Ремонт harness по отдельному разрешению пользователя — валидная I.3

Пользователь после `dd0dd441` разрешил ремонт конкретной тестовой границы,
сохранение invalid runs и один содержательный прогон **без изменения candidate**.
Это отдельное разрешение на технический ремонт после прежнего retry-limit,
не автоматическое возобновление завершённой попытки и не смена алгоритма.
Разрешены research test harness, новые artifacts и журнал; runtime, candidate,
ports, исходные fixtures/negative expectations не меняются. Заменяемая
ответственность — изготовление read DTO в harness, не read permission.

Evidence: [отчёт ремонта](artifacts/next07/grounded-first/20261004-harness-repair-dd0dd441/SUMMARY_RU.md).

Исправленный путь: наблюдение immutable prepared inventory → существующие
ranked proposals I.2 → штатный `get_project_docs` с current catalog/hash/lifecycle
checks → `ProjectDocsChunk` → `project_context_pack` → whole-original-span read
window. `source_class`, authority, freshness и snapshot не подделываются.
Каждый исходный DTO проверяется через `source_window_eligibility`; raw slice
должен совпадать с исходными offsets. Это local research wiring, не final C.

Первый smoke обнаружил только неверную сериализацию dataclass
`ProjectDocsResult` через `model_dump`; исходный output сохранён. Logger
исправлен на `asdict`, candidate не менялся. Исправленный smoke подтвердил
eligible original `project_doc` и разрешённый read default.

Один содержательный run: **22 PASS / 2 FAIL**, exit 1:

- 8 isolated I.2 checks PASS;
- оба LeaseClient read positives PASS (оба facts доступны как local context);
- 12 mutation controls PASS **после успешного positive**, все negative decisions
  сохранены: project/repository identity, freshness/index freshness, risk/injection,
  lifecycle, span, version/snapshot, path, source class;
- **wrong-state FAIL:** при вопросе disabled допускается исходный enabled default;
  `relation_local_witness` не поддерживает operator `default` этой проверки;
- **restriction FAIL:** после успешного short-source positive допускается unit
  `# LeaseClient\n\nLeaseClient raises \`LeaseExpired\`.\n\n` без поздней строки
  `Only when an operation expires.` из того же источника. Целостность unit и
  известные structural edges не обеспечили сохранение межфрагментного ограничения.

Итог: **harness VALIDATED_LOCAL; текущий неизменённый candidate REJECTED**.
Последние два результата — наблюдения local read decision, не native final
packet и не production leakage. Кандидат/grammar/splitter после failure не
исправлялись. I.4–I.6 и II NOT_RUN; сохранение 49 IDs/partial facts, budget C,
required gates/full suite/unseen/reader NOT_RUN. Grounded evidence переиспользовано
после проверки hashes; нового G run не было. История BLOCKED не переписана.

Один следующий шаг — отдельное решение о новой версии candidate с явно
названными обязанностями wrong-state и preservation; не добавлять regex/rescue
или ослаблять negatives автоматически. Текущий замер завершён, rollout запрещён.

## 9. Продолжение b6e890b6: invalid I.4 wiring

53 PASS подтверждены JUnit и input hashes в
`artifacts/next07/grounded-first/read-repair-JYWxAH/`; повтор не выполнялся.
Пользователь разрешил I.4→I.6, не часть II. Evidence нового замера:
`artifacts/next07/grounded-first/20261004-final-b6e890b6/SUMMARY_RU.md`.
Research-only wiring, без изменения candidate/production: первый MCP capture
вернул TypeError до projection. После исправления dataclass conversion один
retry вернул AttributeError, также до projection. Точный источник второго
исключения не установлен, scoped replacements восстановлены.
Это **BLOCKED: invalid wiring, retry-limit исчерпан**, не algorithm REJECTED
и не доказательство невозможности интеграции в allowed scope. I.4 не выполнена;
I.5 retention/gates/full suite и часть II NOT_RUN. Rollout NOT_AUTHORIZED.

## 10. ed3ec41b: I.4 PASS, substantive I.5 N10 REJECTED

Отдельное разрешение пользователя на исправленный wiring: fast-forward до
`ed3ec41b`, candidate `b6e890b6` byte-identical. Evidence и summary:
`artifacts/next07/grounded-first/wiring-check-l99mJU/`.
Новые wiring unit tests: 26 PASS. Настоящие root-only MCP P1/P2/P3:
**VALIDATED_LOCAL_I4**, final cost 589/613/443, sources 3/3/2;
handler validators чисты, answer_supported/answer_available/edit_ready False.
Default, exception и expiration owner сохранены; partial не выдумал exception.
G evidence переиспользовано после проверки reference hashes.

В I.5 выполнен существующий frozen N10 с working positive из
`test_read_context_admission_boundary.py`. Positive доставлен. Negative
`# storage retention behavior\n\nUnrelated network details.` также доставлен
в final sources, хотя неизменённое ожидание — empty. Этот node не входит
в frozen policy-delta allowlist. Source bytes/validator сохранны; результат
классифицирован как irrelevant context / frozen abstention-policy violation,
не ложный proof и не harness exception. Negative действительно выполнен.

**I.5 REJECTED; I.6 конечный verdict текущего замера REJECTED.**
После содержательного failure algorithm/packer/guards/labels не менялись.
Остальные public controls, paired 80/49-ID/partial retention, focused/gates/full
NOT_RUN по STOP. Часть II NOT_RUN; rollout NOT_AUTHORIZED.
