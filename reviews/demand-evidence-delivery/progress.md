# Delivery R0 → MkDocs05 → Pydantic03: progress

Дата: 2026-10-01. Ветка: `experiment/retrieval-ablation-continuation`.

## Финальная передача: scoped delivery завершена, release gate красный

Финальный полный offline gate завершился на code/test identity после согласованной
корректировки guard:

| Checkout | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Новый baseline (`2eeab8b0` + PR196, без fixes) | 5945 | 31 | 10 |
| Финальный кандидат | 5956 | 30 | 10 |

**30 shared failure IDs;0 candidate-only;1 baseline-only.** Исправлен baseline
test `tests/docs/test_pydantic_direct_context.py::test_original_direct_question_delivers_all_four_strict_mode_controls`.
Остальные failures не скрыты и не объявлены только environment failures.
Full gate **FAILED**, не зелёная release/build приёмка. Сопоставление failure IDs
не доказывает отсутствие всех возможных регрессий или улучшение answerer.

Log: `/tmp/opencode/delivery-final-full-offline.log`.
Сравнение с baseline с сохранением полных parametrized node IDs:
`/tmp/opencode/delivery-final-full-gate-comparison.json`.
Старый intermediate comparison ниже не является финальным результатом.

Финальный manifest41 changed code/test files:
`/tmp/opencode/delivery-final-tested-file-manifest.json`, SHA256
`9e3bdcd43b6ca0e7f4fa08ad85caa8c5ada17a988a52bd2d32acf67bd181a359`.
Он включает скорректированный guard и исключает данный progress. Runtime не
менялся после final80; после него изменился только согласованный test scenario.

Итог текущего milestone:
- R0 выполнен от доступного нового baseline, не от утраченного historical archive;
- MkDocs05/Pydantic03 sufficient через native handler;
- frozen80:43→45 sufficient,0 losses ранее supported claims, budgets/audits чистые;
- guard replacement и replay checks GREEN;32 passed scoped,277 passed/1 baseline
  failure related; full gate0 new failure IDs;
- статус targets: `delivery_fixed`; release: `validation_blocked` на shared gate;
- build отдельно не выполнялся, performance/independent holdout не измерялись;
- На момент проверок commit/push/merge/activation не выполнялись. Пользователь
  затем разрешил локальный commit этой поставки, без push/merge/activation;
  raw evidence в `/tmp/opencode`
  требует отдельного сохранения перед удалением временной среды.

**Остановка по плану:** R3–R6 и новая retrieval/URI серия не начинаются.
Переданы local diff, результаты, manifest и blockers. Исторические rejected/
pending разделы ниже сохранены как ledger и не переопределяют этот итог.

## Согласованная корректировка replacement-сценария: guard GREEN

Пользователь явно согласовал корректировку теста без изменения continuation
runtime и без ослабления защиты. В этом increment изменён только существующий
test `test_old_inspection_uri_survives_replacement_of_unissued_draft_locators`
в `tests/docs/test_contiguous_seed_envelope.py` и этот progress.

Тест теперь отключает early precedence delivery **только в первом call**, вместе
с прежним отключением query-block rescue. Второй call использует настоящий
неизменённый handler. Это создаёт настоящий old/new replacement, а не двойное
потребление идемпотентного locator:
- old URI != new URI — обязательный assert, без skip/раннего return;
- required rule обязательно видимо в final sources второго call;
- canonical audit чистый, token/source caps и flags=False проверяются;
- old URI читается после replacement успешно, с правильным line_start и exact
  source bytes; replay old URI отвергается;
- new URI также читается source-bound, с правильным line_start; replay new URI
  отвергается;
- при отсутствии read_next используется реальный source continuation URI,
  как в прежнем fallback первого call, а не изготовленный reference.

Сохранены все original-byte/replacement проверки. Устаревшее требование fact
именно во втором continuation перенесено на фактический final DTO; source
continuation отдельно проверяется на canonical bytes. Public resource contract,
expiry/read budget, source runtime и classifier в этом increment не менялись.
Diagnostic inventory не менялся: имя существующего test осталось прежним.

Свежие результаты с existing Python и offline/hashseed controls:
- continuation + seed-envelope + native delivery acceptance: **32 passed**;
- две disposable mutation-проверки: отключение final early delivery отвергается
  test; возвращение cached authorized bytes при replay также отвергается test;
  mutations выполнены через temporary mocks, не сохранены в runtime;
- расширенные evidence-set/source/locator/seed/module-cap/component/host/
  condition controls: **277 passed / 1 failed**. Единственный failure
  `test_visible_component_novelty_follows_exact_constraints_before_public_queries[projection_clip]`
  уже воспроизведён на новом baseline (см. paired102 ниже).

Финальный полный offline gate запущен на этом runtime/test code:
`DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0`
existing Python `-m pytest -q --tb=short`.
Log: `/tmp/opencode/delivery-final-full-offline.log`.
На момент этой записи результат **PENDING**, не PASS.
Related log: `/tmp/opencode/delivery-final-related-controls.log`.
Предыдущие блокирующие записи ниже — история, не утверждение, что исправленный
replacement test по-прежнему red. Commit/push/merge/activation не выполнялись.

## Ограниченная проверка continuation-контракта

Пользователь разрешил только выяснить связь guard failure с delivery-правкой,
без изменения continuation runtime, frozen guard и без новой серии experiments.
В этом increment изменён только данный progress; product/test code не менялся.

### Факты

- `_source_continuation_core.py:142–147`: `read` извлекает cursor через `pop`.
  Повторное чтение одного URI возвращает `unknown_or_expired_reference`.
  Это предусмотренная consumption protection, а не новый дефект кандидата.
- `issue_range:116–125`: повторная выдача того же authorized range идемпотентна;
  не обновляет expiry/read budget. Два одинаковых вызова до чтения не обязаны
  порождать два разных доступных ресурса.
- Guard `test_old_inspection_uri_survives_replacement_of_unissued_draft_locators`
  отключает первый query-block rescue, но не новый early-delivery route. Он
  предполагает, что два calls выдадут разные locators и что required rule будет
  доставлено вторым continuation, а не непосредственно в final sources.

Один bounded diagnostic с настоящим handler и исходным MkDocs case:

| Наблюдение | Early delivery включена | Early delivery временно отключена |
|---|---|---|
| Rule видимо в sources первого/второго calls | да / да | нет / нет |
| Old URI равен new URI | да | нет |
| Old read после обоих calls | complete, точные original bytes | truncated, точные original bytes |
| Затем new read | отказ повторного read | complete, содержит rule |
| Canonical audits обоих calls | чистые | чистые |

Следовательно старый issued reference **не отозван вторым call**: его первое
чтение успешно. Guard падает из-за двойного потребления одного cursor и своего
ожидания rule в continuation. Зафиксированный первый diagnostic attempt также
показал отсутствие `read_next` в одном budget-dependent packet; затем runner
использовал fallback к source URI, как сам existing guard. Это не замена native
question/corpus и не дополнительный quality benchmark.

Команда: existing Python `-m pytest tests/docs/test_source_continuation.py
tests/docs/test_contiguous_seed_envelope.py::test_old_inspection_uri_survives_replacement_of_unissued_draft_locators
-q --tb=short` с offline/auto-vectors/hashseed controls: **17 passed / 1 failed**.
Все17 continuation tests проходят; тот же scenario test всё ещё red.

### Решение и точная граница

Обновление lifecycle URI **не обосновано**, delivery-код ради двойного чтения
одноразового cursor не менять. Предыдущее название `rejected_regression`
сохранено ниже как результат gate, но диагностика не подтверждает нарушение
source authorization/consumption contract. Актуально: targets `delivery_fixed`,
приёмка `validation_blocked` на несовместимом ожидании existing scenario test.

Scenario test не переписан и не отключён, зелёная приёмка не заявлена. Если
отдельно согласовать его корректировку, она должна по-прежнему проверять:
1. настоящий replacement двух **разных** locators, а не случайно одинаковый URI;
2. первый old read после replacement успешен и source-bound;
3. требуемое rule действительно доставлено источником/continuation;
4. replay одного consumed URI отвергается, expiry/read budget не обновляются.
Нельзя заменить это на безусловный `if same_uri: return` или удалить assertions.
Без такого согласования текущая scoped работа завершена передачей blocker;
runtime URI redesign и новая серия retrieval не начинаются.

Artifacts: `/tmp/opencode/delivery-uri-contract-check.py`,
`/tmp/opencode/delivery-uri-contract-check.json`,
`/tmp/opencode/delivery-uri-contract-tests.log`.

## R1/R2: два native gains; техническая приёмка отклонена

**Текущий статус: `delivery_fixed` для targets + `rejected_regression` для
кандидата. Не готов к merge/активации. Работа остановлена на guard failure,
а не продолжена через изменение frozen tests или расширение архитектуры.**

### Что изменено после нового R0 baseline

- `need_context_projection.py`: существующая checked-context preparation
  отделена от выбора первого fallback. Source/exact/condition admission каждый
  раз recomputed. Precedence/list варианты предлагаются до общего selection.
- Precedence preference требует видимого precedence глагола и текущей
  source-bound eligibility; это ordering, не relation/root proof.
- Для списков рассматривается целая конечная introduced-list структура,
  ограниченная исходным retrieved window и максимумом8 items. Стоимость —
  настоящий DTO. Размер640 chars не применяется к whole-list proposal.
- List preference использует original focus, expected count/category count и
  top-level items. Семантическое соответствие категорий и explanations остаётся
  unverified; это не private `supported` и не full-answer certification.
- `_project_context_service_part01.py` вычисляет checked whole-list context
  перед rerank. `project_doc_ranking.py` сохраняет такие локально проверенные
  candidates без глобального изменения qualifier/ratio. Никакие public/root
  query IDs за context eligibility не выдаются.
- `_docs_context_projection_core.py`: checked варианты входят в конечный
  bounded pool. Typed components имеют приоритет перед context. Extra context
  не вытесняет уже выбранные sources и не обходится без actual token/source caps.
  Explicit path filter сохранён; предпочтение сортировки включается только
  при наличии checked proposals, а не для всех вопросов.
- Сохранены hard policy, public flags=False, schemas, defaults, lock и старый
  corpus/scorer. Поздние reads/search/model calls не добавлены.

### Свежая доставка и retention

Baseline: текущая ablation-ветка `2eeab8b0` + PR196 `dab28032`, `674a4796`, без
R1/R2. Detached worktree `/tmp/opencode/delivery-pr196-baseline`.
Candidate: текущий local diff. Одна и та же existing Python environment,
неизменные80 cases/corpus/assessor, одинаковые case paths в
`/tmp/opencode/delivery-full80-shared`. Созданные runner case directories
удаляются после каждого case; пользовательские каталоги не затронуты.

| Результат | Новый baseline | Финальная локальная реализация |
|---|---:|---:|
| Все исходные cases | 80 | 80 |
| Sufficient | 43 | 45 |
| Needs review | 18 | 16 |
| Insufficient | 19 | 19 |
| Новые supported claims | — | MkDocs05 required, Pydantic03 required |
| Потери любого ранее supported claim | — | 0 |
| Native MkDocs05 | needs_review | sufficient,796 tokens,1 source row |
| Native Pydantic03 | needs_review | sufficient,774 tokens,2 source rows |

Это actual final packets, не gold-selected replay. Все80 native captures прошли
canonical audit, <=800 tokens, <=3 rows, flags=False. Ни assessor, ни frozen
labels не изменялись. Исторические36/48 не представлены как текущий baseline.
Final80 повторяет candidate после ограничений сортировки/explicit-path guard;
ранний candidate pass43→45 сохранён отдельно, не переименован в final.
Не заявляются independent holdout, universal simplification gain или latency gain.
`performance_not_measured`.

### Targeted проверки и mutation controls

- До нового acceptance: existing evidence-set suite177 passed.
- Исходный acceptance:2 failed/3 passed, RED — оба native targets.
- MkDocs mutation: отключение early checked-context proposal возвращает
  `needs_review`; немутированный native packet sufficient.
- Pydantic mutation: отключение checked-set proposal возвращает
  `needs_review`; немутированный native packet sufficient.
- Negative controls: один item, отсутствующий item и вложенный Example не
  получают whole-list proposal. Даже полный структурный список не получает
  private semantic support. Cropped prepared window не доставляет потерянный
  member; proposal generator не выполняет late filesystem/SQLite/socket I/O.
- Partial Pydantic07/Ruff07 сохранены; existing source/version/condition/crop
  controls входят в evidence-set suite.
- Последняя проверка финального code:
  `DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0`
  existing Python `-m pytest tests/docs/test_evidence_set_*.py
  tests/docs/test_python_module_policy_and_manifest.py
  tests/docs/test_source_locator_resolution.py -q --tb=short`: **220 passed**.
- Related projection/ranking suite на предыдущем candidate:297 passed/1 failed;
  request-flow failure отдельно воспроизведён на новом baseline.

### Почему приёмка НЕ пройдена

Парный полный offline gate выполнен до последнего ограничения сортировки,
explicit-path hardening и дополнительных negative tests:

| Checkout | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Новый baseline | 5945 | 31 | 10 |
| Ранний candidate | 5942 | 39 | 10 |

30 shared failure IDs;9 candidate-only;1 baseline-only (старый native Pydantic
delivery test стал проходить). Затем сортировка ограничена checked-context
запросами. Парный related повтор102 tests:
- baseline94 passed/8 failed;
- candidate93 passed/9 failed.
Все падения этого targeted baseline сохранены. В candidate остаётся один новый
guard failure:

`tests/docs/test_contiguous_seed_envelope.py::test_old_inspection_uri_survives_replacement_of_unissued_draft_locators`

Native MkDocs теперь доставляет rule непосредственно в sources. Повторный вызов
воспроизводит тот же continuation `read_next` URI; тест читает old URI, затем
пытается прочитать идентичный new URI. Второй read возвращает
`unknown_or_expired_reference` (одноразовый cursor), без `snippet`.
На baseline test проходит. Это подтверждённая несовместимость кандидата с guard,
не разрешение переписать guard и не доказательство source disclosure.

Frozen guard **не изменён/не отключён**, assertion не ослаблен. Жизненный цикл
continuation ресурсов не переписан ради двух gains. Final full gate после
hardening не переисполнен: targeted candidate-only failure уже отвергает приёмку.
Build/release acceptance не объявляется GREEN. Нужен отдельный согласованный
разбор continuation contract, прежде чем рекомендовать эту поставку.

### Артефакты

- Runner: `/tmp/opencode/delivery-full80.py`.
- Before packets/summary: `/tmp/opencode/delivery-full80-before/`.
- Final packets/summary: `/tmp/opencode/delivery-full80-final/`.
- Intermediate packets: `/tmp/opencode/delivery-full80-after/`.
- Final controls: `/tmp/opencode/delivery-final-controls.log`.
- Current candidate code/test manifest (40 changed files, path+SHA256):
  `/tmp/opencode/delivery-tested-file-manifest.json`, SHA256
  `173221b2865cad7c7622b1e1375f98cd2dfc0f3b0673ac993e717b9cc02d8e48`.
  Manifest excludes this progress document. Full-gate intermediate code is not
  claimed to have this final identity.
- Full logs: `/tmp/opencode/delivery-full-offline-before.log`,
  `/tmp/opencode/delivery-full-offline-after.log`.
- Targeted paired logs: `/tmp/opencode/delivery-regressions-before.log`,
  `/tmp/opencode/delivery-regressions-check.log`.

Summary SHA256:
- before: `099a055263562447c2c969326e8e887898cf022ccf8ed62f82036602dc02fd9c`;
- final: `08f5c663d3caec3e5a5c583b357390f4bc6ecd7d534e56fd1728edda4d53d4dd`.

Изменения остаются local/uncommitted (PR196 import частично staged).
Commit/push/merge/активация в этом increment не выполнялись. Raw artifacts в
`/tmp/opencode` не являются долговечным published archive.

## Возобновление R0: доступный PR196 вместо утраченного checkpoint

Пользователь разрешил продолжать текущую ветку без старого архива. Исторический
блокер ниже сохранён как история; он больше не запрещает работу от нового baseline.

В текущую ветку применены без commit изменения двух доступных PR196 commits:
`dab28032` и `674a4796` через `git cherry-pick --no-commit`. Автоматическое слияние
прошло без конфликтов. Ablation и существующие изменения сохранены. Это новый
интегрированный baseline, не восстановление `d13bf4a` и не активация в main.

Использована существующая среда:
`/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python`.
Новые зависимости не установлены, lock не менялся.

Свежие результаты:
- `python -m pytest tests/docs/test_evidence_set_*.py -q` **до** добавления новой
  acceptance suite: **177 passed**, 6.21 s.
- Добавлена `tests/docs/test_evidence_set_delivery_acceptance.py` и её diagnostic
  registration. Native fixture действительно индексирует corpus, вызывает handler,
  проверяет canonical audit и использует прежний assessor.
- Новая acceptance suite: **2 failed / 3 passed**. RED — MkDocs05 и Pydantic03,
  фактический `context_sufficiency=needs_review`. GREEN — partial-факты
  Pydantic07/Ruff07 и synthetic precedence distractor-control.
- MkDocs05 final: navigation lines99–107 + introduction; rule остаётся в read_next,
  не в sources. Pydantic03 final: Dataclasses/TypedDict section433–476 вместо списка.
  Следовательно старое конкретное описание Pydantic final нельзя повторять как
  результат этого baseline. Full coverage у Pydantic03 не означает sufficiency.
- Bounds проходят для всех четырёх native cases. Full80/полная техническая приёмка
  пока не запускались; claims о retention ограничены двумя partial controls.
- Повтор acceptance с сохранением stdout/stderr:
  `/tmp/opencode/delivery-r0-acceptance.log`, exit1.

Статус: **R0 baseline reproduced; R1/R2 ещё не исправлены**.
Следующий шаг — native MkDocs05: trace существующего prepared pool и integration
до semantic-only culling. Нельзя объявлять R1 GREEN на synthetic control: он уже
проходит на неисправленном baseline. R2 после R1. Никаких новых experiments.

## R0: BLOCKED_CHECKPOINT

Начальный status чистый. HEAD `2eeab8b01884b36b210769498b96e67f09f71f2e`;
runtime tree `4c83871e407c239817114930257dd97624dc79e9`.
Продуктовый код, tests, lock и defaults в этом increment не изменены.

План исполнения:
`/home/viadmin/Загрузки/DocAtlas_delivery_WEAK_MODEL_PLAN_RU.md`.
Объём: только R0 → native MkDocs05 → полный native Pydantic03 → приёмка.
Запрещены новые эксперименты, переписывание архитектуры и ослабление guards.

### Фактическая сверка

- В текущей ветке отсутствуют `need_contracts.py`,
  `need_context_disposition.py`, `need_context_projection.py`,
  `tests/docs/_evidence_set_fixtures.py` и evidence-set acceptance suite.
  `_reference_binding_fixtures.py` есть, но это не полный delivery-checkpoint.
- Локальный Git не содержит `d13bf4a831d2e16348b3622b680f0d62ee0908f4`.
- Целевой поиск delivery/T06 файлов в Downloads и основном checkout
  `/home/viadmin/StudioProjects/hermes/docmancer` не нашёл checkpoint-комплект.
- Просмотр имён файлов пяти DocAtlas ZIP в Downloads не обнаружил T06,
  evidence_set, need_context, need_contracts или delivery_acceptance файлов.
  Архивные scripts не исполнялись.
- `git ls-remote origin` доступен. PR196 имеет head
  `674a4796c8a49dad305a1a22f11711fa07b5574a`.
- `git fetch --no-tags origin refs/pull/196/head` успешен. Read-only просмотр
  дерева обнаружил часть delivery modules и `_evidence_set_fixtures.py`.
  Fixture использует native handler через `observe_call`, canonical audit и
  прежний `assess_context`. Это потенциальный исходный материал, не подтверждение
  полноты исходного tested checkpoint и не новый результат tests.
- `git fetch --no-tags origin d13bf4a831d2e16348b3622b680f0d62ee0908f4`
  завершился `upload-pack: not our ref`.

Delivery-план прямо различает uploaded-but-uncommitted tested tree и PR196.
Поэтому PR196 не импортирован и не объявлен эквивалентным baseline. Сравнение
деревьев показывает также различающиеся runtime/eval paths: полная замена
checkout удалила бы сохранённые ablation-результаты и другие изменения.

### Результаты и ограничения

Native targets и baseline controls **не запускались**: R0 identity prerequisites
не выполнены. Это не assertion RED, не delivery gain и не acceptance PASS.
R1/R2 не начаты. Performance not measured. Merge/push/activation не выполнялись
в рамках этого increment.

### Необходимый следующий вход

Предоставить `DocAtlas_evidence_sets_T06_GitHub_checkpoint_20260922.zip` с
`T06-current.bundle`, `T06-RESUME.json`, original manifest/checksums, runtime tree,
закреплённым corpus/questions/старым assessor; по возможности также
`DocAtlas_delivery_acceptance_tests.py`.

Альтернатива: указать доступный полный delivery-checkout/архив с этими assets
и проверяемой identity либо явно согласовать PR196 как **другой** исходный baseline
с новой приёмкой его состояния. Не выдавать такую замену за восстановление d13bf4a.

После получения входа продолжить R0 в этой же ветке, сохранив ablation-файлы:
проверить manifest и runtime, получить настоящие native target outcomes, затем
минимальные R1/R2 fixes. Не создавать недостающую архитектуру с нуля.
