# M2: исполнительный TDD-план без новых моделей

2026-10-02. Для исполнителя, которому нужны маленькие задания и явные запреты.
**Это план, не отчёт о выполнении. Ни один шаг здесь не объявлен пройденным.**
Основа: [исследование](M2_MODEL_FREE_RETRIEVAL_RESEARCH_RU.md) и
[контракт](M2_SIMPLIFICATION_CONTRACT_RU.md).

## Цель и единственный маршрут

Заменить competing relevance decisions в **project-doc lexical read path**:

```text
verified request/source policy
  → contextual source passages
  → один FTS5 BM25 order
  → exact source-window inventory
  → один read selector в прежний DTO budget
  → final source/applicability rechecks
```

Support/coverage и permissions остаются отдельными. Library retrieval,
dense/sparse/hybrid, explicit change/patch и source-continuation contracts не
переписываются. Ветвление по явному route/intent допустимо; по словам вопроса,
названию библиотеки или benchmark ID — нет.

**Исполнитель не выбирает другую архитектуру.** Grounded используется как
reference принципа, не как новый сервер/dependency. Никаких Qwen, MMR,
TextTiling, aliases, перевода, generated queries и новых lexical исключений.

## Правила исполнения

1. Выполняй **один пронумерованный шаг за запрос**, затем остановись.
2. Внутри шага: один behavioral test → Red → минимальный Green → соседние
   controls. Не пиши весь алгоритм до первого падающего теста.
3. Red должен показывать нарушение указанного поведения. Ошибка environment,
   collection/import или отсутствие fixture не доказывает behavioral defect.
   Для новой API допустим минимальный stub, затем отдельный behavioral Red.
4. Не подменяй ranking, qualification, admission, selector или packet в
   acceptance-тесте. Observer/spies допустимы без изменения результата;
   запретительные mocks допустимы для проверки отсутствия I/O/legacy calls.
5. Не меняй gold, frozen questions/source bytes, evaluator, budgets или ожидаемые
   negatives. Не добавляй xfail/skip/ignore, не ослабляй assertions.
6. Нельзя писать `if mkdocs`, `wins → override`, `require_pair=False` только для
   relation или другой route-specific rescue. Нет новых словарей/threshold tuning.
7. Не делай глобальный `qualify_evidence=True`, не игнорируй guards и не выдавай
   score за вероятность support. Новый read context не получает qualified IDs.
8. Не активируй новое индексирование в пользовательском storage. Все проверки
   — в отдельных fixture/state directories. No push/merge, no auto-cleanup
   пользовательских файлов, no commit чужого working tree.
9. Если для Green нужен файл вне allowed scope, изменение policy или limits —
   **остановись с конкретным blocker**, не расширяй задачу сам.
10. Новые tests зарегистрируй в действующем diagnostic inventory по его правилам;
    label не должен исключать их из regression. Это не разрешение переклассифицировать
    старые failures в PASS.

Общие правила [README](../roadmap/search-quality-2026-10-01/README.md#общие-правила-для-coding-агента) сохраняются.
Для этого design не выполняй параллельно старые шаги 07–09 или исторические arms.

## Два обязательных решения, которые TDD не может придумать

**Gate R — ресурсы, до шага 02.** В принятом manifest зафиксировать численные
passage target/hard limit, candidate count, hydrated-byte limit, window count,
per-source/module caps и deterministic tie-break. Из существующей конфигурации
можно наследовать значения только явно и с указанием единиц. Нельзя скопировать
500/1500/5000 chars Grounded или 768/1280 старого coarse arm как «оптимальные».
Public limit остаётся **800 whole-DTO admission tokens / максимум 3 sources**.
Если выбранные значения превышают прежние resource bounds — нужно отдельное
согласование. Не прятать рост внутренних bytes за прежним DTO budget.

**Gate A — read relevance/abstention, до шага 05.** Нужен согласованный общий
predicate/decision table для фактических visible windows. Включить positive
paraphrase, heading/link-only, question echo, scattered terms, wrong subject,
missing condition и partial known fact + unresolved private tail.
В том же контракте зафиксировать один window ordering/packing objective,
правила структурной полноты и ties. Формулировки «выбери полезное» недостаточно:
исполнитель не придумывает utility formula или новый lexical scorer.

Это реально открытая часть, не задание слабой модели «придумай семантику».
Например, текущий `test_local_topic_witness_rejects_heading_echo_and_scattered_terms`
требует пустой public packet для `storage behavior retention is documented.`;
BM25 может ранжировать его высоко. Одновременно правильный MkDocs paraphrase
нельзя отвергать за отсутствие adjacent pair. **Простой top-k не решает обе
обязанности автоматически.** Если единый критерий не согласован — шаги 05–09
BLOCKED, production replacement не завершён.

Контракт Gate A обязан различать source eligibility, read relevance,
applicability и proof. Для unknown — текущая fail-closed semantics, не automatic
admission. Перестановка terms сама по себе не доказывает ни наличие ответа,
ни его отсутствие.
Любая предлагаемая смена existing negative semantics — отдельное решение,
не исправление теста исполнителем.

## 00 — зафиксировать настоящий baseline и разрешённый scope

**Allowed:** только новый execution manifest и captures вне checkout; runtime
не трогать. Manifest: `v2plan/EXECUTION_RU.md`.

- Сохранить `git status --short`, HEAD, diff hashes, interpreter/import paths,
  source-manifest hash, test inventory и environment limitations.
- Сейчас HEAD `2ffb84fe`, но есть четыре изменённых production-файла. Baseline
  только из HEAD не представляет working tree. Не коммитить/откатывать draft
  автоматически; согласовать baseline snapshot и ownership до правок.
- Последний `require_pair=False`/`sentence_pattern` draft не принимается за
  проверенную policy. Отдельно перечислить его diff и запросить решение,
  не смешивать cleanup этого draft с новым retrieval.
- Запустить focused controls на выбранном baseline; записать actual failing
  node IDs. Исторические 147 failures не являются актуальным PASS/списком причин.
- Составить active-callers map от project request до публикации packet.
  Включить `docs_context_projection.py:284–289`: после core действуют
  `select_joint_context`, `select_query_block_context`, `select_query_block_recovery`.
  Отдельно обозначить checks/I/O/publication/URI duties каждого caller.

**Done:** baseline воспроизводим, ownership/scope подтверждены, известные blockers
названы. Не переписывать runtime из-за ошибок environment. Сначала показать
manifest; Gate R и Gate A нельзя считать согласованными по умолчанию.

## 01 — выделить source eligibility, не меняя qualification

**Allowed:** `docmancer/docs/domain/evidence_qualification.py`,
`docmancer/docs/domain/query_reference_binding.py` при необходимости,
новый `docmancer/docs/domain/source_window_eligibility.py` и tests.

**Red:** в новом `tests/docs/test_source_window_eligibility.py` подготовить
настоящий indexed snapshot через существующие fixtures и проверить:

1. Safe/current exact source window проходит **source check**, даже если
   whole-query lexical qualification отказала; qualification всё ещё отказывает.
2. Wrong project/version/scope/path, stale/dirty/archived, risk flags, changed
   document hash, неверный span и другой request binding не проходят.
3. Подделанные incoming `qualified/context_eligible` flags ничего не разрешают.
4. UTF-8 bytes/char spans согласованы; повторяющийся paragraph нельзя связать
   с первым совпадением через `raw.find(snippet)`.

**Green:** вынести существующие source-policy/reference-binding checks в pure
shared helper. `EligibilityDecision` содержит eligibility/reason/span binding,
не score/qualified IDs/coverage. Не копировать отдельный ослабленный validator.
Сохранить старые qualification outputs и hard exact/subject/condition обязанности;
последние не переименовывать автоматически в «необязательную релевантность».

**Controls:** `tests/docs/test_evidence_qualification.py`,
`test_context_constraint_roles.py`, `test_read_context_admission_boundary.py`,
`test_shared_context_proposals.py`. Прогон на baseline и после refactor должен
сохранять прежние решения, кроме нового guard-only API. Этот шаг — не admission fix.

## 02 — построить contextual search passages отдельно от display children

**Precondition:** Gate R принят. **Allowed:**
`docmancer/core/structured_chunking.py` для переиспользования boundaries,
новый `docmancer/core/retrieval_passages.py`, новый `tests/test_retrieval_passages.py`.
Не менять `ChunkingConfig` defaults, children identity или vector inputs.

**Red:** proposed tests, по одному:

- `test_adjacent_rule_and_topic_share_a_bounded_search_passage`: topic paragraph
  и соседнее short rule внутри одного owner доступны в search representation.
  Gold rule используется только assertion, никогда builder input.
- `test_search_passage_does_not_cross_source_or_owning_subject`: смена source,
  snapshot, scope/version или sibling subject разрывает допустимое объединение.
- `test_display_spans_remain_verbatim_and_independent`: длинный search block
  не становится обязательным public snippet; child bytes/IDs прежние.
- `test_passage_limits_unicode_and_repeat_identity`: deterministic IDs,
  char/byte/line spans, cap boundary и одинаковые абзацы в разных местах.
- `test_oversized_atom_is_not_silently_presented_as_complete`: oversized
  list/row/condition не режется с потерей restriction под видом intact fact.

**Green:** pure deterministic builder из уже parsed source structure. Passage —
contiguous snapshot span с provenance и profile identity. Никаких summaries,
translated annotations, query-dependent chunks или дополнительных source reads.
Непомещающиеся structural dependencies явно incomplete/deferred, не supported.

**Controls:** `tests/test_structured_chunking.py`,
`tests/test_contextual_indexing.py`, `tests/test_parent_child_vectors.py`.
**Done:** новый search representation есть, публичный маршрут ещё прежний.

## 03 — включить passages в атомарную index generation

**Allowed:** SQLite schema/ingest/active-generation shards в `docmancer/core/`,
passage builder и новый `tests/test_retrieval_passage_index.py`.
Не менять child/vector schemas и старые IDs ради passage index.

**Red:** real SQLite, не fake ordered list:

1. Passage record/FTS видимы только в complete active generation.
2. Failed rebuild сохраняет прежнюю generation и extracted source snapshots.
3. Metadata-only edit обновляет promoted policy/context; неизменные source
   bytes сохраняют соответствующую identity по принятому контракту.
4. Local edit/prune не оставляет старый hit; одинаковый text разных projects
   нельзя дедуплицировать с потерей identity.
5. Missing/incompatible passage profile требует preparation, не silent fallback
   к legacy read ranking и не query-time автоматическую reindex.

**Green:** search passages и их FTS принадлежат existing generation transaction.
Отдельная таблица допустима как representation, не второй runtime scorer/server.
Политика metadata filters та же; child/dense index остаётся неизменным.
Profile hash участвует в freshness/readiness. Migration не объявляется accepted
путём подделки validation flag.

**Controls:** `tests/test_parent_child_index.py`, `tests/test_clear_rebuild_lifecycle.py`,
`tests/test_pre_hydration_source_policy.py` и storage/generation controls из map 00.
**Done:** rollback/rebuild/current-generation tests пройдены, user storage untouched.

## 04 — один BM25-порядок для candidate retrieval

**Allowed:** новый passage query API в SQLite store, project-read dispatcher
entry point, новый `tests/test_lexical_passage_retrieval.py`.
Остальные retrieval modes сохраняют прежнее поведение.

**Red:** real FTS index + самостоятельный SQL ranking oracle:

- Порядок API равен BM25 lower-is-better + принятому stable tie-break, с теми же
  fields, query и metadata filters. Сравнивать до/после configured cap отдельно.
- Смена insertion order не меняет ties. Score/rank передаются без
  `1-index*0.05` и без повторного умножения downstream.
- Ручное продвижение нового parent, heading-only distractor или repository path
  и legacy boost helpers не переставляют BM25 order. Совпадения heading могут
  естественно влиять на declared FTS score, но не дают proof. Запретительный spy на эти
  helpers доказывает отсутствие вызова, не заменяет результат поиска.
- Original Unicode question/explicit lookups сохранены; compiled FTS expression
  экранирован. Кавычки и technical identifiers не превращаются в добавленные needs.
- Wrong metadata отфильтрована **до top-k/hydration**; ошибка metadata fail closed.
- Candidate count/bytes соблюдены, giant first hit не получает «бесплатного»
  превышения budget, пустой query не даёт весь corpus.
- Frozen MkDocs rule присутствует в native candidate pool. Не требовать top-1
  любой ценой и не использовать expected witness в ranking.

**Green:** FTS candidate generation + один BM25 order + identity-preserving dedupe
+ existing agreed caps. Не делать project read через старый supplement/body/
parent rerank поверх нового score. Plain body-count ranking не равен этому шагу.
Positive search hit ничего не сертифицирует.

**Controls:** `tests/test_pre_hydration_source_policy.py`,
`tests/test_sqlite_ranking_truth.py`, `tests/test_retrieval_diversity_policy.py` и
hybrid/library tests из map 00. Legacy unit expectations остаются для своих
действующих routes; новая policy не активируется глобально ради удаления helper.
**Done:** candidate recall и ordering доказаны отдельно; final delivery ещё не PASS.

## 05 — общий read-window decision, только по принятому Gate A

**Allowed:** `docmancer/docs/application/read_context_admission.py`, shared
source helper, существующие applicability checks и новый
`tests/docs/test_passage_read_decision.py`. Не менять proof thresholds/grammar.

**Red:** перенести approved Gate A cases в одну parameterized decision table.
Одинаковый proposed window должен получать одинаковое решение независимо от
typed/precedence/list/original-read происхождения. Добавить mutation controls:

- heading/link-only, echo и scattered negatives; faithful paraphrase positive;
- hard literal/subject вне финального окна не авторизует окно;
- missing condition/negation/exception не наследуется от search block;
- known partial context + private tail сохраняется только при неизменных
  bindings/applicability; tail остаётся unresolved;
- source/risk/span/request mutation после prefit вызывает повторный отказ.

**Green:** ровно approved общий predicate; source eligibility + applicability
не зависят от request shape. Решение только `allowed/rejected/unknown` с reason,
не `supported`. Prefit передаёт provenance/window proposal, не cached permission.

**Стоп:** если Green требует нового relation regex, word-count floor, synonym
dictionary или ослабления existing negative — Gate A не решён. Покажи
контрпример и остановись; не переходи к 06. Не считать safe + BM25 достаточным.

**Controls:** unchanged `test_read_context_admission_boundary.py`,
`test_context_constraint_roles.py`, `test_source_bound_subject_context.py` и
public negatives первого rejected trial. Existing failures показывать отдельно.

## 06 — один window inventory и selector в заданный DTO budget

**Allowed:** существующие `context_blocks.py`, `context_windows.py`, pure
window/selection modules, новый `tests/docs/test_passage_window_selection.py`.
Не подключать новый postprocessing rescue после selection.

**Red:** проверить не только наличие слов, а фактические bytes/relations:

1. Search block может не помещаться целиком; компактное source-bound окно
   проходит budget и сохраняет нужный topic/rule/condition. Labels только в tests.
2. Prefit и final получают один и тот же finite inventory/decision contract.
   При changed bytes final пересчитывает, не читает incoming approval.
3. Полный list с intro, table key/header/row и code restriction не проигрывают
   обрезку до недоказанной части; непрерывные spans не склеиваются через holes.
4. Ordinary useful read window может конкурировать в **непустом** packet,
   а не только при `if not sources`.
5. Полный serialized DTO ≤800 по `docs_context_budget_tokens`, sources ≤3;
   metadata cost учитывается, tiny budget не открывает fallback/full parent.
6. Deterministic ties, окна без дубликатов, bounded counts, никаких source I/O
   или resource registration во время предложения/оценки alternatives.
7. Qualified/proof/readiness flags не получаются из source score или span closure.

**Green:** один selector над exact windows. Использовать утверждённый ordering/
packing contract, не изобретать сумму BM25 разных queries или новый utility
threshold. Raw BM25 от разных query/indices не считать одной calibrated шкалой.
Если agreed objective не определён или теряет существующий partial fact — STOP.

**Controls:** `test_context_projection_boundaries.py`, `test_joint_context_invariants.py`,
`test_docs_context_budget_reserve.py`, `test_evidence_set_context_delivery.py`.
**Done:** selector проверен изолированно; ещё не end-to-end замена.

## 07 — подключить новый project read path и вывести старые competing callers

**Allowed:** только project-read orchestrators из утверждённой map 00:
`_project_docs_service_part03.py`, `_project_context_service_part01.py`,
`project_doc_ranking.py`, `docs_context_projection.py`,
`_docs_context_projection_core.py`, `need_context_projection.py` и adapter нового
selector. Каждую границу переносить отдельным red/green micro-step.

**Red:** новый `tests/docs/test_passage_retrieval_delivery.py`, через настоящий
service/index, без replacement ranking и handcrafted qualified payload:

- Неизменённый `mkdocs-05`: original query → retrieval → prefit → projector →
  **public snippet с исходным rule**, valid snapshot, ≤800/≤3, false support/edit flags.
- `httpx-07`, `pydantic-07`, `ruff-07`: нужные known partial facts видны,
  private configuration не «поддержана». Новый positive не оправдывает их потерю.
- Public packet остаётся empty для всех требуемых heading/echo/scattered/source
  negatives. Отсутствие только preferred proposals — недостаточный assertion.
- Дополнительные unchanged positives по lists, tables, exceptions и code;
  scope=project/module/all и explicit version/path не расширяются.
- Invocation trace: targeted read route не вызывает additive/manual/body/parent
  ranking, qualification-as-read-veto, shape-specific rescue или три прежних
  independent final selectors.

**Green:** переключить targeted route в изолированной ветке на единый inventory/
selector. Не оставлять «если новый не нашёл, запусти старый» fallback. Guard,
applicability, structural completeness, URI publication и continuation duties
старых callers перенести/сохранить до их retirement. Не отключать downstream
модули целиком для change/library paths.

**Refactor:** удалить действительно dead read orchestration после caller search
и теста отсутствия вызова. Не оставлять новую схему поверх старой ради локального
Green. Shared helper не удалять, если он ещё выполняет обязанности другого route.

**Done:** native public delivery/negative assertions и active-call retirement
подтверждены. Тест `test_shared_context_proposals.py`, который подменяет ranking
на plain, не является новым native acceptance; сам старый тест не ослаблять.

## 08 — парная регрессия одной реализации

**Allowed:** execution report, новый runner для выбранного baseline/candidate
при необходимости и новые output directories. Runtime tuning здесь запрещён.

- Только два сравниваемых состояния: согласованный baseline и реализованный
  candidate. Не добавлять plain/tied/section/coarse/no-boosts матрицу.
- Одинаковые frozen source bytes, questions, policy, physical corpus identity,
  DTO budget и evaluator. Profile/внутренние resource costs явно фиксировать.
- Для всех claims сравнить candidate recall, retention и public witness delivery.
  `needs_review` не PASS. Частичные facts считать отдельно от within-budget positives.
- Проверить guard violations, false admission/abstention, exact citation/span
  correctness, counts/bytes и packet cost. Не оценивать ответы, которых не генерировали.
- Полный `tests` baseline/candidate: saved logs, node-ID diff, классификация
  каждого нового failure. Старые failures не считать obsolete без разбора.
- Legacy-policy tests, требующие retirement конкретной эвристики, вынести на
  review; не удалять/переписывать самостоятельно ради green suite. Их behavioral
  обязательства перенести в новые acceptance tests после отдельного решения.

**Стоп:** новый guard/negative failure или потерянный previously supported fact.
Не спасать кейс новым исключением. Если failure выявляет противоречие contract,
вернуться на Gate A/R отдельным согласованием, а не менять criteria в этом run.

## 09 — installed MCP, независимая приёмка, затем rollout

**Allowed:** isolated wheel/environment, new evidence/report artifacts;
переключение пользовательского storage/defaults только отдельным approval.

- Собрать/установить candidate в отдельный environment разрешённым способом.
  Сохранить source revision+diff digest, package version, wheel hash и import path.
- Реальный Docs MCP stdio: `scripts/docs_mcp_stdio_smoke.py` плюс native
  MkDocs/partial/negative cases. Generic smoke не заменяет их. Запуск вне checkout
  должен исключать случайный импорт исходников вместо установленного wheel.
- Проверить same-process prepare→query→clear→rebuild и old resource URIs,
  source change, scope/version isolation, permissions, unchanged tool schema.
- Независимый held-out corpus/reader review не подбирает spans по gold и не
  возвращает failures исполнителю для lexical tuning. Без него M2 открыт.
- Reviewer отдельно проверяет relevance/ответ/citations/abstention; source
  validation отдельно. Число runs и frozen-80 улучшение не заменяют этот gate.

**Done:** all gates accepted и rollout явно разрешён. До этого результат может
быть реализован в ветке, но не называться production fix или закрытым M2.

## Команды проверок и формат сдачи

Сначала зафиксировать `PYTHON` — absolute path утверждённого interpreter.
Не предполагать, что системный Python имеет dependencies. В командах ниже
`<STEP_TEST>` заменить только тестом/модулем текущего шага; run directory
создаётся отдельно под `/tmp/opencode/`, старые captures не перезаписывать.

```bash
"$PYTHON" -m pytest -q <STEP_TEST>
"$PYTHON" -m pytest -q tests/test_structured_chunking.py tests/test_parent_child_index.py tests/test_pre_hydration_source_policy.py
"$PYTHON" -m pytest -q tests/docs/test_read_context_admission_boundary.py tests/docs/test_context_constraint_roles.py tests/docs/test_source_bound_subject_context.py
git diff --check
```

Не все команды нужны каждому шагу: выполнить его own tests и перечисленные
controls. Полный suite — шаг 08, с сохранением полного stdout/stderr и exit code.
Installed smoke — шаг 09, установленным interpreter вне checkout. Labels и
collection failures не обходить `-k`, если этим исчезает обязательный control.

Отчёт после каждого шага:

```text
Шаг: NN; статус PASS / BLOCKED / REJECTED
Baseline: revision + diff digest + interpreter
Red: command, node ID, expected behavioral failure, log
Green: command, result, log
Controls: commands, failures до/после
Changed files: список; какое старое read decision заменено
Guards/queries/budgets: подтверждение неизменности, не декларация
Не доказано / blocker: конкретно
Следующий шаг НЕ начат
```

## Готовый первый запрос слабой модели

> Прочитай `v2plan/M2_MODEL_FREE_RETRIEVAL_TDD_RU.md`.
> Выполни только шаг 00: зафиксируй actual baseline, ownership изменённых файлов,
> focused controls и active-callers map. Production-код не меняй, чужой diff
> не коммить и не откатывай. Gate R/A не выбирай сам. Покажи отчёт установленного
> формата и остановись. Без новых моделей, зависимостей, benchmark arms, push/merge.

Для следующих заданий явно заменять номер и разрешённые файлы. Перед 02 нужен
approved Gate R; перед 05 — approved Gate A. Исполнитель не пропускает gate
только потому, что следующий numbered step существует в этом плане.
