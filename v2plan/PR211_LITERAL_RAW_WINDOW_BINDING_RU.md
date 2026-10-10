# PR211: исходный literal window и координаты видимого фрагмента

## Статус и граница доказательства

Узкое исправление подготовлено от опубликованного HEAD `0065ce62cacaa31a41e4567717e3c67d602f578b`.
Четыре изменяемых code base и отдельный relation crosswalk повторно прочитаны именно на этом HEAD и совпали с manifest ниже.
Это статически проверяемый draft; собственного нового runtime receipt пока нет.
Следующий acceptance: normal recovery **12/12**, затем **43 intended kills** (39 прежних + 4 новых), без errors/skips и с точным guard каждого fault.
Прежние успешные receipts не объявляются доказательством этого нового кода.

Фактический [AgentDeveloper job 114127987827](https://github.com/Vanilla1999/DocAtlas/actions/runs/38023053266/job/114127987827) относится к PR HEAD `d76f6ab85e12f482ad6bec1d43040899f4b0a532`.
GitHub checkout — merge `8120a80bbb0309a3ec0bf4add71f568666c76772`, tree `63bff21aadbfb131082db075ed95ea7e89310e44`; равенство tree с PR HEAD отдельно проверено root.
Короткий лог: 86759 байт UTF-8, SHA-256 `b4e7b41c8b424863d90b93a525ce99d9558a62f9a8be7b3bf8b721b19819af83`.
V1 target closed — **8/11**, module-only expected evidence rate — **0.25**; V2 — **24/28**, errors — **0**.

Четыре V1 gaps — исходные stores/requirements/whereas/CatalogReader facts.
V2 содержит первые три и отдельный `project_policy_detail_fails_closed` о ProjectRetryPolicy; CatalogReader не подменяет этот четвёртый V2 случай.
В этом логе отсутствует native per-member admission trace для этих gaps. Связь конкретного MISS с найденным span defect пока является source-level объяснением, а не доказанным actual first-loss.
Comparison остаётся отдельной обязанностью: этот slice не добавляет новую comparison-форму и не заявляет её исправленной.
Frozen questions, facts, paths, protocol, catalog и negative cases не меняются.

## Подтверждённый дефект и исправление

Текущий `prepare_reference_probe` в `query_reference_binding.py` (blob `06215d1e4deaa4c56a2c0afac135bd2f2a29a858`) проверяет текущий immutable source, затем вычисляет `visible = evidence_text.strip()`.
Его `reference_visible_span` описывает этот единственный видимый substring, а не весь acquired body.

Текущий native chunker `structured_chunking.py` (blob `89528de2cb78820ca244924d5be39a94164355de`) сохраняет исходные `content[start:end]`, включая LF/CRLF.
В старом admission четыре закрытые ветки сравнивали длину trimmed span с `len(evidence_text)`, а затем использовали trimmed start как начало raw text.
Внешний LF отвергался; при ведущих пробелах простая замена длины дала бы неверные offsets.

Новый private `_checked_raw_body_window` вызывается после прежней canonical qualification.
Он вычисляет raw start вычитанием ровно ведущего whitespace и raw end по неизменённой длине тела, проверяет строгие integer bounds, containment внутри current candidate/reference window, точное равенство raw substring телу и reference text исходному документу.
Нового поиска occurrence нет: сохраняется прежняя unique-visible проверка.
SHA, owner, project, generation, catalog, lifecycle, source identity и policy проверки остаются до fallback.

Все четыре закрытые ветки (один literal, count, Explain, filename statement) используют один raw origin.
Символьные reference-bindings также требуют этот проверенный raw window: если literal witnesses существуют, а window отсутствует, admission отвергается.
Иначе explicit-symbol ветка могла бы обойти отказ на обрезанном внешнем LF.

Private `body_window` возвращается только для `literal_symbol_body_context`.
Ordinary partial-body admission, её receipt, matcher и прежний formatter путь не изменяются.
Qualification и original coverage остаются false; witness не становится answer/edit authority.

В core только эта проверенная literal ветка восстанавливает **полный raw snippet** после локального вызова `_docs_source`.
Глобальный formatter не меняется.
Char/byte/line offsets вычисляются из того же проверенного raw document; line_end берётся по последнему включённому символу, поэтому завершающий LF/CRLF не создаёт несуществующую EOF+1 строку.
Исходный source material для evidence_id/digest сохраняется; raw snippet передаётся в тот же projected snapshot.
Continuation locator привязывается обычным существующим путём. Native control сверяет source URI с captured snapshot, если URI присутствует в final public DTO.
Existing post-projector binder вправе удалить unavailable optional URI; все non-URI поля обязаны совпадать всегда.

## Native oracle и фактический объём дополнительной работы

Сохранены **все четыре исходных тела** OrdersDraftStore/PaymentOutbox/RelayBufferCell/DispatchInvariant и все восемь ранних positive native reads; весь прежний gate восстанавливается удалением четырёх объявленных wiring deltas.
Новых pytest functions и новых outer recovery cases нет.

Добавляются **2 actual native reads**, **2 explicit finite member preparations** и **3 projection-only replays**.
Это реальная дополнительная работа, а не сокращение числа проверок за одним wrapper.
Она выполняется внутри существующего `closed_literal_context`, без нового job, dependency, provider или network path.
Старый read-only state guard учитывает оба новых публичных вызова.
Обе новые source layout сохраняют исходную question и fact interior:

| Layout | Тело | Независимые диапазоны |
| --- | --- | --- |
| `lf_tail` | исходный OrdersDraftStore fact + LF | char [0, 86), UTF-8 [0, 86), line 1..1; literal [0, 16) |
| `leading_crlf` | SPACE + TAB + исходный RelayBufferCell fact + CRLF | char [0, 59), UTF-8 [0, 60), line 1..1; literal [2, 17) |

Control проверяет точные wire bytes; полный source SHA и independent local owner из captured host project root; current catalog/member/scope; исходные char/byte/line bounds; canonical trimmed span; raw literal witness; отсутствие derived role/original credit; реальный snapshot validator и public/snapshot source agreement.

Первый replay использует здоровый LF capture и меняет **только** candidate char_end на один символ, оставляя полное body, immutable reference, owner и hash.
Обрезанный внешний LF обязан дать пустой valid negative projection.

Два остальных replay используют тот же acquired источник с отдельно authored ``What does `OrdersDraftStore` do?``.
Current `build_documentation_query_plan` и `resolve_references` строят DTO для этого input на фактически captured single-member source.
Healthy projection должна сохранить полный raw fact с наблюдаемой explicit symbol body binding; затем обрезание только char_end должно отвергнуться.
Это не выдаётся за native retrieval этой второй question и не получает query coverage.
Дополнительного read/index для quoted replay нет.

| Layout | Question SHA-256 | Frozen fact SHA-256 | Full acquired source SHA-256 |
| --- | --- | --- | --- |
| `lf_tail` | `b54b6f908431c7d5e9b0e6ece6a75e49e06542ab9dac47757ab67bd339f4141a` | `6f13aec3ccc8d596f1552421aa7f4e0f2f2738b6e9654eeab1621e4a07f704a1` | `6727486dd907578de8b40a8ff0b44193136f2b476cdce1554df80a77c4a08f64` |
| `leading_crlf` | `4307ab3b07496588f43d9f189d8bc161ec4bc1a8a1d3d51b95d766022ba8114a` | `c3fda9f54fd78f160189355df0df3f54119e17f8d8048ca452a4df36e94517b3` | `9b71cdc1dfdc1ce9381dc2214f1ab632a941e106bccc3fc14e2ff7276819b0ac` |

## Directed faults и intended first failure

Каждый fault изменяет один production anchor. Все четыре запускают только existing `closed_literal_context` после обязательного normal baseline.
До named failure выполняются прежние guards и соответствующий здоровый source control.
Полный unmodified 12-case baseline обязателен; import crash, ошибочный guard, skipped case или старый unrelated FAIL не дают mutation credit.

| Fault | Intended guard | Anchor count | Mutated production SHA-256 |
| --- | --- | --- | --- |
| `literal-raw-window-escapes-candidate-span` | `recovery_literal_raw_window_span_replay` | 1 | `23fcb7a0d1156b8c2acf877043b076cdf6ffd7560bdaf8a68a4cb65aea7e9058` |
| `literal-raw-window-uses-trimmed-origin` | `recovery_literal_raw_window_coordinates` | 1 | `16ad826eae05291d5354452c696873e30a3a5658573a843be6e8a1045232ab5c` |
| `literal-raw-window-trimmed-on-wire` | `recovery_literal_raw_window_fact` | 1 | `b980a2c630a46f2ea95453e4350170d8ce2454c9158d779fdfe4746b18ea7830` |
| `literal-symbol-ignores-raw-window-rejection` | `recovery_literal_explicit_raw_window_span_replay` | 1 | `1b559114c24dd53efaa5908e52588b1bf205c1df3ab0e949db41a43f59913cab` |

Первый fault снимает candidate-end containment и допускает raw LF за пределами предъявленного span.
Второй сохраняет raw end, но возвращает trimmed start: только leading-whitespace layout обнаруживает неверные координаты.
Третий возвращает strip на wire и теряет внешний LF до полноты source comparison.
Четвёртый убирает обязательность raw window для already-bound explicit symbol; unquoted replay остаётся отвергнутым, а quoted negative достигает именно своего guard.

Before SHA-256 admission: `b7c4758c43b93c7e794588bb3df76b7e7263df7074e000d99256bdd2d02bd630`.
Before SHA-256 core: `13ea4e153f66d0e22337ac5d3a584a5f55085646b1df78dfad2c95dbf0a274cc`.
Старые **39 Mutant entries** и runner после tuple не меняются.
SHA-256 исходного `MUTANTS = (...)` блока, включая closing parenthesis: `43d395f31c9c3490a81f835155ddaf73fcc3fb10097819b77ac67ba33eea0856`.
TARGET_MODULES и MODULE_PATHS получают только новый helper; совпадающий import inventory становится **18**.
CASE_ROSTER остаётся прежним, evaluator negative controls/exit semantics/timeout неизменны.

## Exact manifest

Все пять code blobs и дополнительный crosswalk созданы и повторно прочитаны; roundtrip byte-exact.
Scripts сохраняют executable mode.
Note — новый `100644`; она не является source proof выполнения.

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `docmancer/docs/domain/literal_context_admission.py` | `100644` | `b94d1508133c51c3a622275f7cbb2a2c802ce1c2` | `2a25313955f125e79666eb386f108e8e94eac7cf` |
| `docmancer/docs/application/_docs_context_projection_core.py` | `100644` | `ec87e90b8ef40faab65e514a3e417ee9d6bf0b0c` | `3dc9c8f19b4431503a073730e1c6f330cd583634` |
| `eval/agent_developer_v1/literal_window_controls.py` | `100644` | `NEW` | `f281d68d81ca6a52d9c8dd093861046f51017f2f` |
| `scripts/run_recovery_contract_gate.py` | `100755` | `8bab7b6c6c33d08e536e7962b08ff476d31e1353` | `30d5006af53b11436075764e52b94b1acbd630d1` |
| `scripts/run_recovery_mutation_gate.py` | `100755` | `ae400a4c8bb442128f28d92e40cc849b7ea1f997` | `3360dce2970cab4f45b180c0fe23c8f13f23db4d` |
| `eval/task_level/contract_history/admission_relation_live_source_inputs.json` | `100644` | `bf9d0c72261231ca006fe19c2fb5c707ea3b88e5` | `063b66cd4b5a42be2d523f8b53d903eb510a6680` |

| Path | Physical lines | Proposed UTF-8 SHA-256 |
| --- | --- | --- |
| `docmancer/docs/domain/literal_context_admission.py` | 323 | `b7c4758c43b93c7e794588bb3df76b7e7263df7074e000d99256bdd2d02bd630` |
| `docmancer/docs/application/_docs_context_projection_core.py` | 998 | `13ea4e153f66d0e22337ac5d3a584a5f55085646b1df78dfad2c95dbf0a274cc` |
| `eval/agent_developer_v1/literal_window_controls.py` | 169 | `f0ed46940c5daf572dc5465473c961aa7bdfe2a73a0b30934770cf82598229b2` |
| `scripts/run_recovery_contract_gate.py` | 1000 | `179fb8828b74c3346e68d6fa31055a1629c6289919a4e138d8d93c50bafb25fb` |
| `scripts/run_recovery_mutation_gate.py` | 394 | `7554e46fe4e89689f39865e2dadd4173a0ebb9664ccd7ae2465814dde9b75282` |
| `eval/task_level/contract_history/admission_relation_live_source_inputs.json` | 234 | `74478cee3bf4696698f5d8924243f9b171c63481ae9a764ee454eb21776082f5` |

## Соседняя relation mutation recipe

`admission_relation_live_source_inputs.json` хранит source hashes для существующего `relation-callable-context-as-answer`.
Owning core изменён этим slice, поэтому обновлены только его `base_blob`, `expected_before_sha256` и `expected_after_sha256`; unique anchor, mutation text, frozen inputs, expected guard/cases/errors/skips и другой relation fault сохранены.
After SHA-256 существующего fault на core3dc: `370f960f0de809289ef3d31b7b3ba04cb47bf063307482c7509e21be59867863`.
Дополнительная запись `mutation_recipe_rebase` явно требует новый same-tree baseline/intended kill и запрещает reuse исторических receipts.
Исторический source_checkout сохранён; runtime остаётся pending. Это обновление metadata не изменяет relation helper или critical runner.
Current helper `relation_source_context_controls.py` (blob `c4ebf2ddb4b6c66669f119efa103de1e4556d422`) независимо сверяет unchanged archive/input digest, а не этот новый recipe record.
Обратное восстановление трёх scalar fields и удаление rebase record даёт base JSON byte-for-byte.

## Inverse review и последующий acceptance

- Admission: удалить один новый helper с его разделительным newline, восстановить четыре прежних span predicates/origins, убрать mandatory literal-window guard и private output field — получается base byte-for-byte.
- Core: обратная замена одного snippet/line-bound блока даёт base byte-for-byte; остальной source неизменён.
- Recovery gate: убрать один import, одну module registration, один helper call и одно report field — получается base byte-for-byte.
- Mutator: убрать одну helper module entry и append-only четыре faults — получается base byte-for-byte.
- Новый helper содержит один вызываемый control, без тестовой collection и без module import side effects.

Независимый static review пяти code blobs завершён APPROVE; дополнительный metadata rebase и обновлённая note переданы на review. Перед публикацией нужен final root review всего manifest.
После публикации нужны actual normal recovery 12/12 и 43 intended kills на одном checkout tree, затем неизменённые AgentDeveloper/P14 и совместные required CI/downstream gates.
До этого нет claims о новом PASS, исправлении четырёх AgentDeveloper cases, готовности PR к merge или сокращении runtime.

## Последующая интеграция source-unit fidelity: новая hash-привязка, PENDING

Этот раздел относится к следующему slice поверх опубликованного HEAD
`a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07` (136). Он сохраняет предыдущий
manifest и все исторические значения этой note: они описывают подготовку
raw-window slice 133, а не новый runtime receipt.

Предлагаемый owning core меняется
`3dc9c8f19b4431503a073730e1c6f330cd583634` →
`0eb803a9105bbb2b4e07e0659eb46b7739725f28`
из-за отбора различных квалифицированных source units.
Новые byte/unit predicates не меняют raw literal window, его formatter,
four raw fault anchors, frozen input bytes или intended guards.

Новый before SHA-256 core:
`866d6154c0d59dd4ab76ea946cb408a2cc440e073f2988f41bdf34ef32837de2`.

| Существующий fault | Source после интеграции | Anchor count | After SHA-256 | Intended guard |
| --- | --- | ---: | --- | --- |
| `literal-raw-window-escapes-candidate-span` | admission `2a253139`, unchanged | 1 | `23fcb7a0d1156b8c2acf877043b076cdf6ffd7560bdaf8a68a4cb65aea7e9058` | `recovery_literal_raw_window_span_replay` |
| `literal-raw-window-uses-trimmed-origin` | admission `2a253139`, unchanged | 1 | `16ad826eae05291d5354452c696873e30a3a5658573a843be6e8a1045232ab5c` | `recovery_literal_raw_window_coordinates` |
| `literal-raw-window-trimmed-on-wire` | core `0eb803a9` | 1 | `5151a8a979b6e1fa6e08e52089d798f7c44eda371ca6e50520996ea782944e9b` | `recovery_literal_raw_window_fact` |
| `literal-symbol-ignores-raw-window-rejection` | admission `2a253139`, unchanged | 1 | `1b559114c24dd53efaa5908e52588b1bf205c1df3ab0e949db41a43f59913cab` | `recovery_literal_explicit_raw_window_span_replay` |

Admission before SHA-256 остаётся
`b7c4758c43b93c7e794588bb3df76b7e7263df7074e000d99256bdd2d02bd630`.
Все четыре count и after hashes повторно вычислены из exact current/proposed
source простой текстовой подстановкой единственного существующего anchor,
без импорта/исполнения Python.

Recovery runner `3360dce2970cab4f45b180c0fe23c8f13f23db4d` и literal helper
`f281d68d81ca6a52d9c8dd093861046f51017f2f` повторно прочитаны на 136;
оба неизменны. У runner по-прежнему 43 faults и строгая проверка actual module
hash, outcome, case и intended guard. Этот раздел не заменяет такую проверку.

Для соседнего `relation-callable-context-as-answer` сохраняется exact anchor
и `critical_relation_public_no_answer_authority`; after SHA-256 на core0eb:
`cdf41b4904080184d4e4cff844008b6afdcbec4de8f70ce36024fe9ba62b5e98`.
В crosswalk изменены ровно три current recipe scalars:
`base_blob`, `expected_before_sha256`, `expected_after_sha256`.
Добавлена `qualified_unit_recipe_rebase` с требованием нового same-tree
baseline/intended kill и `historical_receipts_reused=false`.
Прежняя `mutation_recipe_rebase` сохранена как историческая запись raw-window
интеграции; новый record явно помечает её значение.

Frozen inputs и их digest, archive, другой relation fault, exact mutation text,
guards/counts/errors/skips, historical source checkout и runtime section
побайтно восстанавливаются обратной заменой трёх scalar fields и удалением
новой записи. Relation helper и critical/recovery runners этим metadata slice
не редактируются.

| Descriptive path | Mode | Base blob на 136 | Proposed blob |
| --- | --- | --- | --- |
| `eval/task_level/contract_history/admission_relation_live_source_inputs.json` | 100644 | `063b66cd4b5a42be2d523f8b53d903eb510a6680` | `2e742877e97ecd476b2ffe30965de5f143a9366e` |
| `v2plan/PR211_LITERAL_RAW_WINDOW_BINDING_RU.md` | 100644 | `cb5e3876da557fb625e2e1c2f0088c20fdfb0c2e` | this append-only revision |

Старый текст note сохранён полностью; удаление только этого раздела возвращает
base. Новые recovery 12/43 и critical baseline/все intended kills на конечном
tree остаются **PENDING**. Предыдущие receipts, включая возможный результат
136, нельзя выдать за собственный proof кода core0eb.
