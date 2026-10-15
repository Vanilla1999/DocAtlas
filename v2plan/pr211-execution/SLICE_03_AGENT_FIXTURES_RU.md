# Agent Developer / adversarial: implementation review

Дата: 2026-10-09. База: 11489239ae0a5ff85c1f817f0650bea661e88ba1.
Результат: код и fixtures реализованы; локальный runtime не исполнялся. Для PASS необходим обычный PR CI конечного SHA.

## Изменённые файлы

- `scripts/run_agent_developer_gate.py`
- `scripts/run_agent_developer_adversarial_gate.py`
- `scripts/run_agent_developer_adversarial_mutation_gate.py`
- `eval/agent_developer_v1/expected_trajectories.json`
- `eval/agent_developer_v2/cases.json`
- `eval/agent_developer_v1/projects/ambiguous_modules_monorepo/docatlas.project-docs.yaml`
- `eval/agent_developer_v1/projects/explicit_catalog_monorepo/README.md`
- `eval/agent_developer_v1/projects/explicit_catalog_monorepo/services/catalog/README.md`
- `eval/agent_developer_v1/projects/explicit_catalog_monorepo/services/catalog/src/reader.py`
- `eval/agent_developer_v1/projects/explicit_catalog_monorepo/docatlas.project-docs.yaml`
- `tests/test_product_scope.py` (только agent protocol/model score helper assertions)

`tasks.json`, все 11 historical task IDs/prompts, 28 adversarial IDs и исходные questions/retry questions, все 16 прежних fixture files сохранены побайтно. Новые positive fixture тексты равны исходной autodiscovery fixture. Runtime production, shared index_project helper, project gold, workflows и historical reports не менялись этим slice.

## Действующий контракт и crosswalk

| Прежняя проверка | Текущая проверка | Что сохраняется |
|---|---|---|
| Прямой `handle_context_tool`, mode/project/module hidden parameters | `call_docs_tool_payload` с normal tools/list schema, ownership validation и serializer. Исторический mode остаётся oracle metadata, не посылается серверу. | Исходный вопрос, explicit scope, path, library/version. |
| `autodiscovery_module_supported` без catalog неожиданно индексируется | Тот же public task и вопрос: cold-store `failed/permission_denied`, без sources/authority и без создания app storage. | Отрицательная проверка отсутствия неявного discovery/подготовки. |
| Неявная positive autodiscovery | Отдельный обязательный `migration_controls.explicit_catalog_module_supported`: тот же вопрос/текст, явный finite docs-only catalog, public confirmed member transaction, верный host store. | Полезный CatalogReader fact плюс scope/source/fidelity. Historical task_count остаётся 11; control отдельно учитывается и обязательно проходит. |
| `module=auth` и старый module_ambiguous recovery | Removed input — public `validation_error`. Затем явно запрошенный host `docs_status(details=true,module=auth)`, полный inventory двух (или пяти) exact paths, один authored exact-path retry. | Ни implicit choice, ни cross-module leakage; caller/host, а не server prose, выбирает путь. |
| `module=orders/payments` positive | В соответствующих v2 cases authored working-path binding → точный `module_path`; old selector сохранён как historical metadata. Removed module parameter отдельно покрыт schema negative. | Положительный source/fact guard на том же вопросе. |
| Long/five-auth setup_files auto-discovery | `setup_catalog_documents` явно перечисляет только docs; code files остаются вне catalog. | Exact long path, пять одноимённых module roots, ambiguity и isolation. |
| Stale sync recommendation с legacy with_vectors | Changed member hash: отсутствует context/answer/edit, требуется project_docs_preflight confirmation. Возможная advisory не содержит confirm/mutation/network grant и не auto-executes. | Отказ от stale evidence, отсутствие самовольной записи. Отсутствие suggestion на blocked read допустимо. |
| `mode=dependency` | Public explicit `library=tenacity, version=8.2.3`, pin взят из неизменённого pyproject. Если нет source/network approval, no-context confirmation с причиной source selection или network. | Exact target, отсутствие speculative latest fallback и автоматического prefetch. |
| Status/source filename доказывают ответ | Positive обязан доставить заранее выписанный полный факт из исходного документа; каждый quote проверен по file bytes, координатам, project identity, citation/hash presence. `answer_supported/answer_available/edit_ready` не могут стать true. | Исходная developer task, полезность, все условия и source attribution. |

Content_sha256 в current projection — hash bound candidate, не file hash; oracle не подменяет его другим контрактом. Сравнение actual cryptographic binding выполняет production validator и отдельный member/security suite. Новый guard проверяет наличие 64-hex identity и независимо подтверждает visible bytes/coordinates/project identity.

## Output cost policy diff

| Прежний ceiling | Новое значение в evidence | Решение |
|---|---|---|
| V1 context default 1000 (ambiguity 256) / status 1200 / global trajectory 2000 | Каждая context/status delivery измеряется; сумма и max остаются | Fixed output ceiling удалён. |
| V2 global 2000 | `historical_global_max_trajectory_tokens` | Diagnostic history, не pass/fail. |
| V2 per-case 256–2000 | `historical_max_trajectory_tokens` | Diagnostic history, не pass/fail. |
| V2 per-call и retry `max_projection_tokens` | `historical_max_projection_tokens` | Diagnostic history, не pass/fail. |
| V2 status `max_status_projection_tokens` | `historical_max_status_projection_tokens` | Diagnostic history, не pass/fail. |
| Retired `packet_tokens` input | `historical_packet_tokens` | Не передаётся normal public API. |

Стоимость считается независимо по canonical UTF8 полного DTO с заменой только временного project path на `$PROJECT_PATH`; estimate = ceil(bytes/4). Поле returned estimated_tokens не принимается за стоимость: absent/zero/false estimate не прячет payload. Это estimation evidence, не настоящий tokenizer/client billing. Все original values retained; новых числовых output caps нет.

Operational limits **сохранены**: explicit max_get_docs_context_calls; max24 setup files; max4096 UTF8 input bytes/file. Mutation child timeout 600s добавлен только как execution failure (никогда не kill).

## Mutation strength

Нужны две зелёные baseline: весь public v1 + control + 28 v2 cases и восемь named evaluator positive/negative controls. При красной baseline mutants не засчитываются.

9 целевых mutants: cost measurement, verbatim quote fidelity, forbidden source, exact scope, retry inventory, edit authorization, production exact module path/prefix, status inventory, missing-module reason projection. Два retired output-budget mutants заменены измерением/fidelity; retired module-name ambiguity mutant заменён actual exact-path guard.

Child пишет structured report, imported source paths и hashes. Parent проверяет исходную/mutated разницу, единственный anchor, parsing, hash реально импортированного модуля, неизменность oracle files, полный exact roster/order, все event kinds, отсутствие execution_errors и конкретный ожидаемый failed assertion/case. Произвольный nonzero, import/setup exception, timeout, skip, исчезнувший отчёт, unexpected failing task или no-op mutation дают MUTATION ERROR.

Новые ordinary pytest tests не добавлены: изменены существующие oracle score fixtures и protocol expectations; позитивы/негативы и named controls находятся в существующем gate.

## Выполненные проверки

- AST parsing четырёх изменённых Python files без импортов/исполнения repository.
- Все 9 production/evaluator mutation anchors находятся ровно один раз; AST parsing mutated source успешен.
- JSON parsing; historical11+28 exact question/retry roster совпадает с HEAD.
- `tasks.json` и 16 прежних fixture files byte-identical HEAD.
- Все независимо выписанные positive facts реально присутствуют в исходных fixture docs/setup text.
- Per-case extensions совпадают с набором authored setup Markdown files; module roots точные, code не включён.
- `git diff --check` проходит.
- Audit: `agent-fixtures-static-audit.json`.

## Требуемый runtime/review

1. Запустить current `run_agent_developer_gate.py`/adversarial в ordinary PR CI; проверить реальные delivered facts/source ranges и consent ветки. Setup fix не объявляется gate PASS.
2. Если теперь обнаружена real retrieval loss (в том числе полный факт/conditions отсутствуют), исправлять retrieval boundary или явно оставить красный gate; oracle не ослаблять.
3. Strict mutation baseline обязана стать green перед kill claims. После этого подтвердить точные expected failed rosters для трёх production mutants по JSON artifacts.
4. Часть исторической model/installed инфраструктуры всё ещё использует старую module/mode action grammar и historical11 отчёты; этот slice не утверждает новую provider/client acceptance. Отдельно требуется current-client migration, historical reports не переписывать.
5. Reviewer должен отдельно оценить public schema migration, status inventory host action и cost-policy diff; это не простая замена фактических ожиданий.

## Independent review fix

Reviewer обнаружил обход no-authorization guard через alternate flags при edit_ready=false. _authorizes_edit теперь отклоняет mutation_ready, mutation_authorized, edit_authorized, authorized, authorization_granted, can_edit и nonempty authorized_actions/mutation_actions; malformed non-false grants также запрещены. Retrieval-only call отклоняет nonempty answer/answer_text/final_answer. Existing named edit_authority control расширен соответствующими контрпримерами. AST всех четырёх files и всех девяти mutation anchors повторно проверены; runtime не исполнялся.

Успешный project/module positive дополнительно требует `kind=docs_context` и `context_available=true`. Existing `edit_authority` control теперь содержит и корректный positive DTO, и адресный wrong-kind counterexample: compatibility `docs_answer` с false authority flags не проходит. Проверка nonempty answer привязана к конкретному `retrieval_only_answer` failure, чтобы другой guard не мог скрыть её поломку.

В обоих recovery runners ответ `docs_status` связан с outer `tool=docs_status`, `action=project` и точным `project.project_path`; explicit error/failed state отклоняется. У обычного успешного ответа outer status отсутствует — искусственного требования `status=ok` нет. Existing `retry_inventory` control расширен корректным status DTO и отдельными foreign tool/action/project, failed/error контрпримерами. Имена и число восьми controls, а также девять mutation anchors сохранены; последняя AST/anchor и diff-check проверка прошла, runtime всё ещё не запускался.


## Independent reviewer record

# Agent fixtures — независимый review

Дата: 2026-10-09. Reviewer: `docs_quality_impl`, автор: `agent_fixtures_impl`.
Worktree: `/workspace/scratch/5ecb5f548321/DocAtlas-plan-execution`.
Исходная база slice: `11489239ae0a5ff85c1f817f0650bea661e88ba1`.

## Решение

**APPROVE для интеграции и обычного PR CI.** Открытых implementation blockers по этому slice после исправлений ниже не найдено. Это не runtime acceptance: repository code, pytest, fixture/server subprocesses и provider calls в локальной среде не запускались.

## Что проверено независимо

- Все 11 public tasks сохранены побайтно; все 28 adversarial IDs/order и исходные questions/retry questions сохранены. Проверка выполнена сравнением JSON/bytes с исходным Git commit.
- Три документа/source files отдельного положительного fixture побайтно равны прежнему autodiscovery fixture. Исходный cold task остаётся отрицательным; отдельный `explicit_catalog_module_supported` обязателен и учитывается отдельно, без изменения historical task_count 11.
- 10 V1 и 17 V2 явно выписанных полных фактов найдены в исходных authored fixture bytes/setup text. Их источником служит исходный документ, а не фактический ответ retriever.
- Public вызовы проходят `call_docs_tool_payload`: advertised schema, ownership check, handler и serializer. Удалённые mode/module поля не скрываются за direct handler bypass; legacy module оставлен только как отдельный schema-negative input.
- Подготовка использует finite docs-only catalog и существующую confirmed member transaction. Отсутствие catalog сохраняет cold state и проверяет отсутствие app storage после чтения. Новые fixtures не вводят implicit admission, запись или discovery.
- Положительные результаты требуют полезного полного source fact, source coordinates/visible-byte fidelity, exact project identity и source identity presence. Точный retry module выбирается из явно полученного inventory; authored explicit host request не выдаётся за самовольный выбор сервера.
- Отмена фиксированных output ceilings сохраняет исходные числовые значения в historical metadata. Полный DTO измеряется независимо от returned estimated_tokens. Operational context-call/setup/file-size bounds сохранены.
- Mutation gate требует зелёный полный baseline и восемь evaluator controls, полный roster/order/events, точный ожидаемый failed assertion/case, unchanged oracle hashes и hash реально импортированного изменённого source. Crash, timeout, setup/import exception, skip, missing report и no-op не дают kill credit.
- Все девять mutation anchors независимо найдены ровно один раз; все изменённые варианты разобраны AST без исполнения. Четыре изменённых Python файла разобраны и скомпилированы в code object без исполнения. `git diff --check` прошёл.

## Найденные и исправленные дефекты

1. `edit_ready=false` скрывал альтернативные grants (`mutation_ready`, `authorized_actions` и другие). Oracle теперь отвергает альтернативное право на mutation/edit, malformed non-false grant и непустой server-composed answer. Контрпримеры добавлены внутрь существующего `edit_authority` control.
2. Положительный project/module payload мог иметь compatibility `kind=docs_answer`. Теперь обязательны `kind=docs_context` и `context_available=true`, с отдельным wrong-kind контрпримером внутри того же control.
3. Правильный список module paths мог быть принят из failed или чужого status DTO. Оба recovery runners теперь связывают inventory с `tool=docs_status`, `action=project`, точным `project.project_path` и отсутствием explicit failure/error. Обычный production ответ не содержит `status=ok`, поэтому это поле не объявлено обязательным. Контрпримеры включены в существующий `retry_inventory` control.

Все три исправления перечитаны независимо. Идентичности восьми controls и девяти mutants сохранены.

## Границы решения

`content_sha256` в current projection — hash bound candidate, а не hash целого файла. Новый fixture oracle проверяет наличие корректного 64-hex идентификатора и независимо проверяет текст/координаты/project identity; он не заявляет самостоятельную криптографическую проверку candidate binding. Она остаётся обязанностью production validator и существующих member/security checks.

Реальная доставка полных фактов и реальные consent/recovery ветки ещё должны пройти на конечном SHA. Все девять mutation kills, особенно точные failed rosters трёх production mutants, требуют фактического CI. Старые model/installed client reports этим slice не обновлены и не считаются current acceptance.

## Проверенные исходники

| Файл | SHA256 после исправлений |
|---|---|
| `scripts/run_agent_developer_gate.py` | `187466cba6dc97b3d0433a10d4fe07768840c93d0b4580d9281df639a09dd206` |
| `scripts/run_agent_developer_adversarial_gate.py` | `a7f88031fbb7fb2ac843b1509a82138aea62b996b619c094efec2282726e1cca` |
| `scripts/run_agent_developer_adversarial_mutation_gate.py` | `f2d317946b221f5dab55e9e9a222991abc1c2e00a6d67463aa2c1673977a8e11` |
| `tests/test_product_scope.py` | `41aa29be42350ba8a7bb9080eedbe0786ec4ae152a839386b823bc957cda40da` |

Полный перечень fixtures и policy migration: `agent-fixtures-review.md`; авторский static audit: `agent-fixtures-static-audit.json` рядом с этим файлом.


Root integration: ordinary CI now retains complete v1/v2 JSON reports on success or failure using the existing artifact upload. This adds evidence, not a gate waiver.
