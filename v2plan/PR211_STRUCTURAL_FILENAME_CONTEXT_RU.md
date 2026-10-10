# PR #211: structural filename context

## Статус и границы доказательства

Этот slice добавляет общий способ назвать существующий документ целым именем файла в закрытой форме вопроса. Он не меняет P15 corpus, семь исходных вопросов, тринадцать кандидатов, шесть полных фактов, два отрицательных случая, scorer или oracle.

Последний подтверждённый P15 до этого slice: HEAD `f7b9253c8e477babf276ae8dd2cb18905451cd15`, run `38008532078`, job `114082883391`: **5/7 cases, 4/6 full facts, 0 errors, 6/6 oracle controls**. Остаются `document_statement_binds_exact_path` и `two_claims_require_two_allowed_roles`, оба по `required_full_facts`; library source уже привязан. Для сравнения, на предыдущем HEAD `80c8fbbb3e8c379467a9075f93f7165d080f8432`, run `38006157207`, job `114075319048`, было 5/7 cases и 3/6 full facts при тех же 0 errors и 6/6 controls. Ни один из этих результатов не относится к новому filename коду.

На HEAD `f7b9253c8e477babf276ae8dd2cb18905451cd15`, фактический merge checkout `011e808a0dcd2ec8104611a2257d17b5f20e327a`, run `38008532239`, job `114082885405`, recovery baseline был **11 PASS / 1 FAIL / 0 ERROR**: `closed_literal_context: recovery_explain_literal_source_fact`. Mutation runner правильно отказал негодной baseline в credit; 23 kills тогда не подтверждены. Отдельный report-only printer `a8e9c5b0` сохраняется в данном изменении целиком.

Три production blobs ниже прошли independent static review. Новые helper, runner wiring и восемь mutations переданы на отдельный review. Здесь не выполнялись Python/import/AST/pytest/runtime, загрузка моделей или провайдеров. **Ни новый baseline PASS, ни 31 kill, ни закрытие PR не заявлены.** Existing failed Explain guard должен остаться FAIL до фактического исправления причины; код не обходит его ради новых сценариев.

## Контракт

Принимается только полностью разобранная форма:

`What does the <whole filename label> say about <one bare unresolved identifier>?`

Регистр служебных слов формы несущественен. Регистр имени и идентификатора, исходный вопрос и их символьные координаты сохраняются. Идентификатор должен уже существовать как ровно один исходный bare unresolved mention; явная цитата, дополнительный предмет, отрицание или хвост не получают этот маршрут.

Имя выводится только из целого basename stem существующего документа с поддерживаемым расширением. Допускается обратимая структурная запись разделителей: одиночные ASCII `-`, `_` и пробел между словами stem соответствуют одиночному пробелу в label. Casefold, CamelCase splitting, stemming, перестановка, синонимы, заголовки, описания, тематические keywords и частичные совпадения не используются. Например, `queue-window.md`, `queue_window.md` и `queue window.md` называют label `queue window`; если два таких пути разрешены одновременно, имя неоднозначно.

Уникальность считается по всем текущим разрешённым записям naming inventory, включая одинаковые bytes и пути вне возвращённых кандидатов. Проект, lifecycle, module, scope, freshness и path-safety ограничивают inventory. Явный `evidence_path` ограничивает acquisition, но не убирает коллизию имени из этого inventory. Ни ranked winner, ни dedup по body hash, ID или basename не могут превратить коллизию в единственный источник.

Producer создаёт inventory из app-owned SQLite snapshot, а не из metadata пришедшего chunk. Consumer независимо проверяет структуру, полный scope/source/path/hash, digest и текущую source membership, заново выполняет resolution на всём inventory и сравнивает полный reference roster: mention bytes/offset/explicit, role, state, reason и source IDs. Самосогласованный digest и объявленный один победитель недостаточны. Target должен остаться unresolved.

Bridge использует только свежий canonical qualifier binding с `syntax=structural_filename`, полной identity и точным body witness. Source phrase не засчитывается как body fact. Требуется исходный identifier в содержательном body paragraph, а не только в имени, heading, ссылке, префиксе другого символа или identifier-only строке. Witness сохраняет raw body/query offsets, включая Unicode.

Результат — доступный источник как context с `coverage_credit=False`. Полный original query остаётся unverified/missing; не выдаются answer/edit, policy, tool или lifecycle authority. Существующие source owner/member/hash/generation/window/operational проверки предшествуют этому пути. Ни общий token ratio, ни scoring, ни public schema не изменены. Inventory остаётся private evidence, не копируется в публичный payload.

## Владельцы и сохранённые пути

| Файл | Ответственность |
|---|---|
| `docmancer/docs/domain/query_reference_binding.py` | Закрытая форма, структурное имя, inventory schema/digest, независимый полный повторный resolution и typed reference validation |
| `docmancer/docs/application/source_reference_evidence.py` | Naming inventory до evidence-path filter, legacy retrieval sources после него, app-owned detached proof |
| `docmancer/docs/domain/literal_context_admission.py` | Context-only bridge от свежего source binding к точному substantive body witness |
| `eval/agent_developer_v1/structural_filename_controls.py` | Независимая finite fixture и проверки через существующий recovery case |
| `scripts/run_recovery_contract_gate.py` | Вызов helper в существующем case, расширенный executed-module manifest |
| `scripts/run_recovery_mutation_gate.py` | Восемь новых направленных faults; прежний baseline и exact guard verification |

`query_mentions` и `_source_ids` сохраняют прежние literal/path/quoted-source правила. Legacy source selection не переходит на новый глобальный naming roster. В production не добавлены SQL запросы, новые retrieval calls или чтение внешних файлов.

Source audit: `_project_docs_service_part03.py` blob `14075c0e78996c610004e17c4db7d4d61cc3077f` создаёт path filter только из явного evidence_path и строит SourceReferenceContext до acquisition. `_sqlite_store_part01.py` blob `37cdc16685c1f2bc479e59b4ab2a737506b05fe0` имеет PK `(generation_id, source)` и immutable owner validation при upsert. Новый naming list собирается до path-filter и не использует legacy source dictionary для подсчёта коллизий.

## Независимая native fixture и oracle

Fixture не содержит имён, фактов или путей P15. Используются `ArchiveEpoch`, `manual/queue-window.md` и противоположный факт в `manual/queue-notes.md`. Точный вопрос: `What does the queue window say about ArchiveEpoch?`. Исходные body bytes включают `λ`, чтобы проверка raw character offsets отличалась от UTF-8 byte offsets.

Подготовка использует действующие `write_project`, `index_project`, `isolated_service`; asserts требуют точный finite indexed roster без excluded/failed/unexpected paths. Действующий `_apply_project_members` — upsert с `sources_deleted=0` и `recreate=False`, поэтому изменённый roster получает отдельные временные host-selected store и project через ExitStack. Уменьшение каталога не считается разрешением удалить старый индекс. Изменения body при прежнем roster выполняют настоящий последующий member transaction в том же store. После переключения collision fixture сначала проходит normal public read, чтобы прямой scope probe использовал её фактический текущий read store. Каждый public read проходит существующий реальный `_observed_public_call`, projected snapshot validator и before/after generation + SHA-256 fingerprints project/storage файлов. Фикстура не передаёт ожидаемый полный факт в question или requirements.

Helper добавлен к существующему `closed_literal_context`; имена двенадцати cases и ordinary pytest test roster не расширены. Helper и binding module включены в проверяемый executed-source manifest. Исходный gate остаётся меньше 1000 строк.

План исполнения нового helper:

- Шесть structural positives: исходный/current-restored документ, пробелы и регистр frame, underscore/space separator, отдельный exact-case `.rst` path.
- Два прежних literal source routes с path и quoted stem + explicit body identifier.
- Двадцать пять native negatives: directory/extension/separator collisions, частичные/переставленные/case-modified labels, negation/extra subject/tail, отсутствие/регистр/префикс/heading/link/identifier-only body.
- Один explicit path-filter probe на том же реальном read store. Единственный acquisition path обязан оставить оба разрешённых имени в naming inventory.
- Один native acquisition observation намеренно не возвращает второй реальный collision candidate после ровно одного исходного вызова на каждое перехваченное обращение к dispatcher. Проверяется, что реально были и retained, и withheld chunks, и полный producer inventory остаётся двучленным. Это явно управляемая fixture, не утверждение о случайном top-k.
- Двадцать malformed capture controls: missing/incomplete/integer-complete/boolean-schema inventory; malformed rows/fields; foreign scope; текущий source hash; duplicate identity/path; unsafe path; digest; missing source reference/span/source-ID container; missing/list/dict/forged target role.
- Отдельный self-consistent collision replay меняет второй catalog path, пересчитывает digest и сохраняет forged single-winner plan. Consumer обязан независимо увидеть ambiguity.
- Существующие тринадцать immutable owner/source/scope/hash/generation/window/operational replay controls повторяются на здоровом native capture.

По структуре helper ожидается 33 public reads, один отдельный path-scope read, 17 confirmed preparations в 11 изолированных finite fixtures и 21 новый replay сверх прежних 13. Это инвентаризация кода, **не runtime receipt**. Отрицательный public сценарий требует нормальный docs-context payload без error; crash/empty handler failure не считается защитой. Replay требует валидный отрицательный projection, без source/snapshot/context/authority.

## Направленные мутации

Все прежние 23 mutations сохранены побайтно. Новые восемь применяются по единственному source anchor и обязаны дать failure соответствующего guard, а не import/setup/error. Existing runner требует полностью зелёную baseline и exact imported source hashes прежде mutation credit.

| Mutation | Предполагаемый первый guard |
|---|---|
| `filename-nomination-disabled` | `recovery_filename_source_fact` |
| `filename-collision-first-winner` | `recovery_filename_catalog_ambiguity` |
| `filename-global-recheck-only-current-source` | `recovery_filename_global_recheck` |
| `filename-target-role-not-rechecked` | `recovery_filename_reference_roles` |
| `filename-frame-ignores-extra-clause` | `recovery_filename_complete_syntax` |
| `filename-partial-stem-becomes-locator` | `recovery_filename_whole_label` |
| `filename-casefold-becomes-locator` | `recovery_filename_whole_label` |
| `filename-path-filter-hides-collision` | `recovery_filename_path_selection_not_naming_scope` |

Directory collision выполняется раньше forged-winner replay, чтобы first-winner mutant не зависел от сортировки ID. Existing Explain/count controls и mutations остаются перед filename helper и не ослабляются. Цель общего runner после успешной baseline — 12 cases / 31 intended kills; если реальная baseline FAIL, этот целевой результат не принимается.

## Review manifest

Все изменения существуют как GitHub blobs; refs/commits выполняет root после review. Recovery base включает отдельно одобренный printer.

| Path | Mode | Base blob | Proposed blob |
|---|---|---|---|
| `docmancer/docs/domain/query_reference_binding.py` | 100644 | `61257ce508a737d4fa21a2580b49673f5c900ec5` | `06215d1e4deaa4c56a2c0afac135bd2f2a29a858` |
| `docmancer/docs/application/source_reference_evidence.py` | 100644 | `50283806f4e6e101b8f99172cea191e981edf24e` | `14e8916cd686ad237440b3e6aa1da60e2c7ea191` |
| `docmancer/docs/domain/literal_context_admission.py` | 100644 | `0dc5fb950bd3d4a5893e195baefb01897e3aa525` | `7e84697c04beb394ec561252d36bd78f3695fc3d` |
| `eval/agent_developer_v1/structural_filename_controls.py` | 100644 | NEW | `f31fb0fdc9e970a04fa14f9a97e3c22ea74c3c23` |
| `scripts/run_recovery_contract_gate.py` | 100755 | `a8e9c5b0c0588e281eec7532ac5016f3aaaeb6be` | `a3f9269526848a0f32d652ec7a88c9a54bdbe991` |
| `scripts/run_recovery_mutation_gate.py` | 100755 | `64c5d9f96e0009d3fbec5929cbfe7b607600d7a5` | `08a9b8da959a86637415f8c66fa13fe2bffb4357` |
| `v2plan/PR211_STRUCTURAL_FILENAME_CONTEXT_RU.md` | 100644 | NEW | this note |

Static preparation checked exact GitHub roundtrips, unique mutation anchors and inverse edits restoring previous gate/mutation code. These checks are not Python syntax/runtime proof.

## Acceptance

После independent review требуются actual same-checkout recovery baseline, directed mutations, P15 quality + source/full-fact/read-only/oracle controls, P14/P16 and final closure. Проверки должны исполнять и сверять именно опубликованные source hashes. Текущие failure причины, required CI, downstream и installed/client gates сохраняются. Fixture подтверждает Python MCP handler/projection/capture path; она сама по себе не доказывает stdio delivery, installed wheel/client или LLM execution.

## Root review после independent review

Root прочёл полный final helper `f31fb0fd`, точные gate/mutation diff и
подтверждённую native fixture API. Оставлены 12 case names, все23 прежних
mutation blocks и13 immutable guards. Readonly review отдельно исправил
смену catalog roster через новый явно выбранный temporary store; это не
удаление старых indexed sources. Root независимо сверил33 public reads и
25 native negatives. Source slices APPROVE; actual Explain baseline и31
intended kills всё ещё PENDING.
