# PR211: четвёртое независимое review A/B/C

Дата: 2026-10-06. Worktree: `/tmp/opencode/pr211-parallel-review`.
Ветка: `diagnostic/pr211-independent-review-20261006`.
HEAD: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.

## Решение

- **B: REJECT для продуктового переноса / HOLD для доказательства полезной регрессии.**
  Одноусловное вмешательство и authoritative-first потеря текста подтверждены.
  Однако объявление потерянного текста реально нужным ответу недостаточно обосновано.
  Это не основание принять B: безопасность расширенного исключения supporting не доказана.
- **C: ACCEPT как ограниченные supplemental behavioral checks, не как завершённый
  crop/merge/forged audit. Миграция старого теста — HOLD, требуется отдельное owner approval.**
  Публичная original-attribution в normal anchor-only сценарии не обнаружена.
  Существующие assertions не переписаны, FAIL сохранён.
- **A: BLOCKED после разрешённого продолжения review.** Реальная числовая цитата
  теряется на другом формате документа; подробности и независимые команды ниже.
  В первоначальном B/C review A оставался PENDING и его незавершённая работа не читалась.

Ни один результат не означает готовность PR к merge; «0 новых failure IDs» не
доказывает отсутствие регрессий в содержимом успешных packets.

## B: что подтверждено и что блокирует сильный вывод

Прочитаны authority REPORT, полный `authority_diagnostic.py`, replay, исходная fixture,
evidence JSON; повторный запуск проведён на локальной копии в reviewer worktree.
Tracked diff authority worktree пуст; все диагностические файлы untracked.

`authority_diagnostic.py:17–23` удаляет ровно один guard
`and query_plan.get("component_scope_complete", True)` и сохраняет native globals через
FunctionType. Это корректнее отдельного globals namespace и не смешивает A/C.
`useful` отличается от distractor добавлением одной фразы, остальные 24 notes,
manifest, вопрос и ranking не меняются. В обеих ветках authoritative выбран первым,
план неполон. Baseline доставляет `A changed hash produces a red warning.`, candidate
теряет её; rejection `authority_duplicate` и false answer/edit flags проверены.
Исходный notes test независимо воспроизведён: baseline FAIL, candidate PASS.

**Блокер B1 (семантика контрпримера):** исходный вопрос спрашивает *exact contract*,
governing EvidenceRequirementSet, SupportDecision и decision_hash. Note прямо сообщает,
что не определяет acceptance contract; новая фраза не называет decision_hash, субъект
warning и его отношение к запрошенному нормативному контракту не заданы. Текст тематически
связан и содержит новый наблюдаемый факт, но это ещё не строгое доказательство потери
нужного запрошенного факта. REVIEW-критерий «реально нужный факт» нельзя заменить
assertion на presence произвольной добавленной строки.

Независимый локальный контроль добавил к тому же вопросу явное
`What warning is shown when the hash changes?`. Все восемь packets сформированы,
полезная фраза сохранена и baseline, и B. Supporting в useful стал первым;
assertions прежнего стенда завершились exit 1 (также нарушено ожидание неполного плана).
Это **не** authoritative-first positive control и **не** доказательство безопасности B;
оно показывает, почему вопрос/порядок/parser надо проверять одновременно.
Файл и evidence этой неудачной контрольной попытки сохранены, успехом не названы.

Independent lookup действительно выбирает supporting первым, same-source проверяет
доставку тела, а не механизм same_origin_gain. Отчёт B честно указывает эти ограничения.
Вывод: расширение запрета не принимать; сильный «доказана потеря нужного ответа»
ограничить до «доказана потеря нового тематического текста». Нужна новая request-relevant
authoritative-first пара без специальных ranking/parser исключений.

## C: реальность seam и ограничения доказательства

Hint worktree также имеет пустой tracked diff. Новый тест и manifest прочитаны целиком.
Dispatcher.run подменяет только выдачу lanes/candidates, а anchor lane вызывает native
dispatcher над реально индексированным документом. `capture_public_call` наблюдает
настоящий `call_docs_tool_payload` и возвращает реальный transport-validated packet;
observer вызывает исходную projection. Это содержательный pipeline seam, не forged
final packet. Original lane намеренно пуста: валидный anchor-only контроль, но не
полностью неподменённый end-to-end retrieval.

Normal/crop/merge packets реально имеют anchor covered, original missing, partial
coverage, SQLite и false authority flags. Foreign/unrelated/forged отказывают без
sources. Нет skip/xfail, старые assertions и бюджеты не менялись. Hash-bound shard
добавляет только новый module, существующий fail-closed manifest loader не изменён;
полная коллекция нового module прошла inventory validation.

**Блокер C1 (crop):** assertion `len(final snippet) < len(text)` сравнивает с целым
документом, не с входом projection. Независимый observer показал: до projection
`content` уже 73 символа (`# Storage` + BODY + два newline), final 71 символ.
Длинная housekeeping часть отсечена раньше; здесь нет содержательной потери видимого
факта на final crop. Отдельная ручная подстановка snippet в `_requalify_visible_source`
полезна как unit control, но не закрывает final-public crop regression. Нужен контроль,
где production projection действительно сокращает поступившее окно, с pre/post
содержимым и attribution после сокращения; не увеличивать бюджеты ради примера.

**Риск C2 (merge):** duplicate identical chunks и self-merge traces проверяют dedup и
тождественный merge. Нет доказательства выполнения heterogeneous-window merge или
continuation с конфликтующими admission-only/qualified traces. Ограничение в отчёте
признано; нельзя подписывать этим весь merge boundary.

**Риск C3 (forged):** forged trace внедряется в dispatcher до qualification. Проверка
показывает, что такая ранняя подмена не приводит к final выдаче; она не устанавливает,
что forged trace достиг финального requalification/merge (мог быть заменён раньше).
Не обобщать её на все lineage fields. Отказ unrelated/forged допускает отсутствие
edit_ready, что соответствует реально наблюдаемому отказу, а не снятию старого assertion;
на success checks поле также стоит требовать явно, как обещает отчёт.

Предложение миграции в REPORT C не применено и не прогонялось как новый старый тест.
Новая жёсткая строка query-anchor-1 остаётся representation dependency. Рекомендация:
отдельное owner approval и затем согласованный тест с behavioral distinction
discovery/qualification/public attribution; не автоматически заменять фактические IDs
на gold. Полноту crop/merge audit пока не принимать. Продуктовый patch C не нужен по
измеренному normal сценарию, но общий security proof отсутствует.

## Точные независимые команды / результаты

Все команды ниже из reviewer worktree; копии взяты из B/C только для локального
воспроизведения. Другие worktrees и primary tree не изменялись.

```sh
cp /tmp/opencode/pr211-parallel-authority/authority_diagnostic.py ./authority_diagnostic.py
cp /tmp/opencode/pr211-parallel-authority/authority_test_replay.py ./authority_test_replay.py
cp /tmp/opencode/pr211-parallel-hint/tests/docs/test_pr211_hint_public_audit.py tests/docs/test_pr211_hint_public_audit.py
cp /tmp/opencode/pr211-parallel-hint/tests/diagnostic_labels.pr211_hint_audit.json tests/diagnostic_labels.pr211_hint_audit.json
```

Каждый Python вызов имел одинаковый prefix (ниже сокращён только для читаемости):

```sh
DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=/tmp/opencode/pr211-parallel-review /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python
```

Аргументы и redirection после этого prefix:

```sh
authority_diagnostic.py > reviewer-authority.log 2>&1
authority_test_replay.py -q tests/test_docs_service_part03.py::test_project_query_does_not_return_non_project_docs_with_same_terms > reviewer-notes-baseline.log 2>&1
# Для следующего вызова дополнительно AUTHORITY_CANDIDATE=1 в env:
authority_test_replay.py -q tests/test_docs_service_part03.py::test_project_query_does_not_return_non_project_docs_with_same_terms > reviewer-notes-candidate.log 2>&1
-m pytest tests/docs/test_pr211_hint_public_audit.py tests/docs/test_discovery_independent_qualification.py tests/test_docs_service_part02.py::test_query_project_docs_attributes_generic_retrieval_hints_without_covering_original -q -s > reviewer-hint.log 2>&1
reviewer_explicit_warning.py > reviewer-explicit-warning.log 2>&1
reviewer_capture_probe.py > reviewer-crop.log 2>&1
```

| Запуск | Результат |
|---|---|
| B diagnostic | exit 0, все 8 парных packets, потеря строки воспроизведена |
| исходный notes baseline | exit 1, 1 FAIL |
| исходный notes B | exit 0, 1 PASS |
| C supplemental + independent qualification + старый hint | exit 1, 8 PASS / 1 FAIL, 1.95 s |
| explicit-warning control | exit 1, нарушены предпосылки старого diagnostic; факт не потерян |
| crop observer | exit 0, 1 PASS / 5 deselected, 1.10 s; pre content 73 / final 71 |
| git diff --check | exit 0; tracked diff отсутствует |

Последняя версия crop observer читает `content`, не отсутствующий `snippet` в
pre-projection pack; исходная неинформативная печать нулевой длины исправлена только
в локальном observer. Полный capture сохранён в `reviewer-crop-capture.json`.

Прочитаны primary `PR211_RED_ANALYSIS_REVIEW_RU.md`, evidence summary JSON и B evidence;
основные выводы проверены новым запуском, чужие заявления о 85/117/full-core rosters
не выданы за собственное воспроизведение. Full core/CI matrix, installed-package,
security/mutation и downstream answer correctness здесь не запускались.
Пробы синтетические, не holdout. Нет commits/push/merge и разрешения на них.
Это завершало первоначальный B/C этап; на тот момент A оставался PENDING.

## Продолжение: независимый review завершённого A

**Вердикт: BLOCKED, не ACCEPT FOR INTEGRATION.** Причинное исправление целевого
adversarial случая подтверждено, но обнаружена новая потеря реально релевантного
числового контекста, отсутствующая в существующем core roster. Никакие findings B/C
выше этим продолжением не сняты; миграция hint по-прежнему требует отдельного approval.

### Scope, tests, manifest и авторские артефакты

После разрешения пользователя прочитан завершённый strict-attribute REPORT,
настоящие git diff/status, полный новый test module и manifest, environment,
paired-core/probes JSON, summarizer и финальные логи/XML. В A worktree изменён ровно
один tracked product file: `_docs_context_projection_core.py:665` добавляет
`and not strict_single_attribute` в условие вызова `project_need_context_fallback`.
Нет иных tracked изменений, переписанных старых tests/gold, guard/limit/workflow diff.
Новые test/manifest и диагностические артефакты untracked. Patch применён через
`patch` только к reviewer worktree; полное совпадение candidate bytes подтверждено
SHA-256 `6205d18bbb2e73d7d8ad2aa1213fa59cb26964b47b63c147d208f49dbd751a32`.

Это сохранение существующего main-path veto на позднем пути, не новый parser:
strict вычисляется из complete component scope, ровно одного attribute obligation
и truthy value_kind (не только number). Main path отклоняет missing component witness
на :248–250; теперь поздний переинтерпретирующий fallback не восстанавливает context.
Рекурсии hints (:680 и :761) получают тот же retrieval/component contract, вычисляют
ту же strict границу; отдельного обходного вызова `project_need_context_fallback`
в docs application поиском не обнаружено. Основная выдача при признанном witness
этим условием не блокируется. Это не глобальное исправление parser/witness качества.

Авторские 13 tests содержательные, без weakening:

- positive plain/heading/mixed-subject/module проверяют реальный финальный snippet,
  path, доступность context и false authority flags;
- negative no-value/OtherWorker/unrelated проверяют и final отказ, и реальное отсутствие
  late call через wraps observer, и missing_attribute trace;
- unknown partial сохраняет исходную bounded-queue цитату, missing original и incomplete
  plan; это реальный positive нестрогого fallback;
- policy corruptions используют настоящую замороженную retrieval, подменяют только
  кандидат, проверяют projection и snapshot. Это meaningful projection-seam проверки,
  не отдельный public-transport end-to-end для каждой corruption;
- вспомогательные native capture fixtures проверяют видимость строк в исходнике,
  snapshot/integrity и прежний 800-token budget. Нового повышения budget нет.

Hash-bound behavioral shard корректен: только новый module, без node overrides и
коллизий; полная коллекция module и inventory прошла независимо. Guards не отключены.
Слабость positive набора: три варианта повторяют один literal ANSWER, включая subject
и точные слова `retry attempts`; heading-вариант не проверяет наследование subject из
heading при другой естественной формулировке attribute в body.

Независимый read-only XML audit (`reviewer_A_evidence_audit.py`) проверил отсутствие
duplicate node IDs до построения dict; авторские core XML действительно дают baseline
5282 PASS / 17 FAIL / 10 SKIP и candidate 5295 PASS / те же 17 FAIL / 10 SKIP.
Ни один baseline node не потерян, ни один existing status не изменён, 13 added PASS.
Advanced XML содержит 622 PASS. Финальные логи согласуются с XML и environment.json;
нет признаков runtime product подмены в описанных `python -m pytest` запусках.
Это проверка сохранённых артефактов, не независимый full-core replay и не доказательство
временного состояния product file в каждом историческом запуске. Автор явно отделил
невалидные ранние core runs и candidate-only advanced/mutation от парного сравнения.

### Блокер A1: воспроизведённый numeric recall loss

Standalone `reviewer_A_formats.py` выполняет native ingestion и настоящий public call,
без замены qualification/dispatcher/projector. Вопрос неизменный:
`How many retry attempts does ProjectRetryPolicy allow?`. Меняется только текст Guide.md.
Один interpreter/offline env; отдельные процессы читают настоящий product file.
Сначала кандидат, затем восстановлен только собственный однострочный patch к baseline,
`git diff --exit-code -- <product>` дал exit 0, затем candidate восстановлен. Итоговые
baseline/candidate captures повторены с фиксацией product hash и Python в каждой строке.

Baseline hash: `3fabbd99b47bb964d253dea96f7ada5d88001e554d1426d4873ee8cfa683103d`.
Candidate hash: `6205d18bbb2e73d7d8ad2aa1213fa59cb26964b47b63c147d208f49dbd751a32`.
Во всех numeric probes обоих вариантов scope complete, один и тот же attribute
contract с subject ProjectRetryPolicy, attribute retry attempts, value_kind number.

| Реальный документ | Baseline final | A final |
|---|---|---|
| `ProjectRetryPolicy allows at most 2 retry attempts.` | ok, число процитировано | то же |
| Heading ProjectRetryPolicy + `Retry attempts: 2.` | ok, число процитировано | то же |
| Heading ProjectRetryPolicy + markdown table Retry attempts / 2 | ok, таблица процитирована | то же |
| Heading ProjectRetryPolicy + JSON retry_attempts: 2 | ok, code процитирован | то же |
| `ProjectRetryPolicy allows the operation to be retried twice.` | ok, полная фраза | insufficient_evidence, sources отсутствуют |
| `# ProjectRetryPolicy` + `The retry policy allows at most two attempts.` | ok, heading и числовая фраза | insufficient_evidence, sources отсутствуют |

Последняя строка — сильный контрпример: явно локальный subject из heading, число
`two`, retry/attempts в одной фразе, нет другого subject, unsafe/stale/foreign источника
или увеличенного budget. Baseline действительно доставляет нужный ответный факт.
Witness detector не признаёт его; A распространяет этот false negative на последний
context route. Это подтверждённая потеря useful context, не предположение о частоте
регрессий и не ложная answer authority (flags остаются false).

`twice` — дополнительная семантическая формулировка числа; ambiguity о first attempt
не меняет того, что полезный факт о количестве повторов перестаёт цитироваться.
Основание BLOCKED прежде всего heading/prose case, не этот дополнительный пример.

### Другие риски и границы

Probe `ProjectRetryPolicy delegates retry decisions to OtherWorker, which allows nine
retry attempts.` выдаётся и baseline, и A. Это pre-existing permissive witness binding,
не новая регрессия A и не обход нового late guard: кандидат допускается основным путём.
Нельзя объявлять однострочный patch полным subject/number isolation fix по negative
тесту, где OtherWorker находится в другом абзаце.

Отдельный explicit lookup к diagnostic command при отсутствии запрошенного числа
также меняется ok → insufficient_evidence. Этот случай требует отдельного решения о
контракте независимого lookup/partial context и не используется как основной блокер.
Новый guard действует при любом отсутствии accepted sources, не только после
missing_attribute: он не различает witness false negative, packet budget и policy
rejection. Другие attribute value kinds почти не покрыты новым числовым модулем;
нельзя обобщать positive coverage на все value_kind или языки.

### Условия снятия BLOCKED

1. Согласовать поведение на обнаруженном heading/prose numeric case: сохранить
   безопасную доставку нужного числового факта или получить явное owner approval на
   этот recall tradeoff. Автоматическое утверждение «baseline был permissive, значит
   любая потеря допустима» не является acceptance.
2. Добавить regression control с этим реальным body и финальной цитатой, не заменить
   его ожиданием отказа, skip/xfail или lexical blacklist/словарём ради данного примера.
3. Любое доработанное source/witness-boundary решение проверять paired на реальном diff:
   no-value/other-subject отказ, recognized numeric positives, unknown partial и новые
   paraphrase/heading controls. Не отключать весь partial fallback и не повышать budgets.
4. Если расширяется scope сверх данного guard, отдельно проверить value kinds и
   independent lookups; не смешивать исправление B или миграцию C в тот же patch.
5. После согласованного решения — обязательный CI/матрица/installed-package и owner
   authorization. Сейчас full CI/merge readiness не заявлены.

### Независимые команды и результаты A

Все команды из reviewer worktree, Python prefix ровно тот же, что указан выше в B/C
разделе (DOCATLAS_OFFLINE/HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE=1 и reviewer PYTHONPATH).
Новые A test/manifest скопированы без правок из завершённого A worktree:

```sh
cp /tmp/opencode/pr211-parallel-strict-attribute/tests/docs/test_strict_attribute_late_fallback.py tests/docs/test_strict_attribute_late_fallback.py
cp /tmp/opencode/pr211-parallel-strict-attribute/tests/diagnostic_labels.strict_attribute_late_fallback.json tests/diagnostic_labels.strict_attribute_late_fallback.json
```

Аргументы после того же Python prefix; смены продукта — только локальный настоящий
однострочный diff, не AUTHORITY_CANDIDATE и не monkeypatch:

```sh
# Baseline product:
-m pytest tests/docs/test_strict_attribute_late_fallback.py tests/test_diagnostic_labels.py -q --junitxml=reviewer-A-baseline.xml > reviewer-A-baseline.log 2>&1
scripts/run_agent_developer_adversarial_gate.py --output reviewer-A-baseline-adversarial.json > reviewer-A-baseline-adversarial.log 2>&1
# Candidate product:
-m pytest tests/docs/test_strict_attribute_late_fallback.py tests/docs/test_quantified_attribute_scope_isolation.py tests/docs/test_context_completion_guards.py tests/docs/test_context_projection_boundaries.py tests/docs/test_joint_context_invariants.py tests/docs/test_evidence_set_context_delivery.py tests/docs/test_source_bound_subject_context.py tests/docs/test_exact_document_fallback_context.py tests/docs/test_context_capture_integrity.py tests/test_diagnostic_labels.py -q --junitxml=reviewer-A-candidate-targeted.xml > reviewer-A-candidate-targeted.log 2>&1
scripts/run_agent_developer_adversarial_gate.py --output reviewer-A-candidate-adversarial.json > reviewer-A-candidate-adversarial.log 2>&1
-m pytest tests/ -m advanced -q --junitxml=reviewer-A-advanced.xml > reviewer-A-advanced.log 2>&1
-m pytest tests/docs/test_python_module_policy_and_manifest.py tests/docs/test_structural_item_integrity.py -q --junitxml=reviewer-A-guards.xml > reviewer-A-guards.log 2>&1
# Отдельно на baseline и candidate product file соответственно:
reviewer_A_formats.py reviewer-A-formats-baseline.json > reviewer-A-formats-baseline.log 2>&1
reviewer_A_formats.py reviewer-A-formats-candidate.json > reviewer-A-formats-candidate.log 2>&1
```

Read-only evidence audit выполнялся `/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python reviewer_A_evidence_audit.py > reviewer-A-evidence-audit.log 2>&1`.

| Независимый запуск | Результат |
|---|---|
| Baseline strict+inventory | exit 1: 15 PASS / 4 FAIL, 3.70 s |
| Candidate targeted roster | exit 1: 121 PASS / 1 прежний request-flow FAIL, 41.15 s; все 13 A PASS |
| Baseline adversarial | exit 1: 27/28, прежний module case, 3 violation messages |
| Candidate adversarial | exit 0: 28/28, violations=0 |
| Candidate advanced | exit 0: 622 PASS / 5328 deselected, 30.62 s; лишние 6 deselected — reviewer C tests |
| Candidate line/structural guards | exit 0: 21 PASS, 0.19 s |
| Baseline/candidate numeric formats | оба exit 0: captures сохранены; два реальных numeric context loss |
| XML evidence audit | exit 0: counts/statuses сверены, duplicate/missing nodes нет |
| git diff --check | exit 0; reviewer tracked diff — только скопированное условие A |

Format probe exit 0 означает успешный capture, **не** acceptance: он намеренно не
утверждает candidate correctness. Полные public packets, планы и traces доступны в
`reviewer-A-formats-{baseline,candidate}.json`; summary — `reviewer-A-evidence-audit.json`.
Advanced warnings не скрыты (тот же python_multipart PendingDeprecationWarning).

Продуктовый baseline/candidate full core независимо не повторялся; mutation и
question-surface gates здесь не повторялись. Существующий core красный и не содержит
найденного numeric counterexample, поэтому его одинаковые failure IDs не снимают A1.
Исходные worktrees и primary tree не изменены, commits/push/merge не выполнялись.
В reviewer worktree оставлен candidate diff только как локальная reproduction.
