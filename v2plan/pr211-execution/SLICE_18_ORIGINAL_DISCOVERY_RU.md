# Сохранение фактического original-query discovery

## Узкий контракт и причина

`_tag_retrieval_query` правильно не доверяет входящим query-trace метаданным: при новой проверке помечает старые traces как `admission_only`. Но `_qualify_candidate_lookups` использовал этот адаптер последовательно на изменённом chunk и пропускал уже существующие traces. Следующий lookup поэтому мог стереть публичный вклад предыдущего original/lookup; подмена этого поведения простым сохранением входящего флага была бы небезопасной.

Изменение сохраняет две отдельные вещи. Фактическую acquisition фиксирует локальный ledger текущего application call. Релевантность заново проверяет неизменённый canonical qualifier для каждого независимого текущего DTO. Ledger сам не квалифицирует факт, не разрешает answer/edit и не создаёт parent/original credit из lookup.

## Файлы

- `docmancer/docs/application/reference_query_tagging.py` — ключ точного приобретённого окна и запись host-owned acquisition.
- `docmancer/docs/application/_project_docs_service_part03.py` — запись реальных completed retrieval calls после canonical source preparation; независимые fresh traces объединяются один раз.
- `tests/docs/test_discovery_independent_qualification.py` — два свойства: сохранение actual original/двух lookup в обоих порядках; отказ от forged original receipt при отсутствии acquisition и подмене path/window/body/scope/generation.
- `tests/diagnostic_labels.global_evidence.json` — новый хеш четырёх имён функций; остальные записи неизменны.
- `tests/docs/test_context_loss_boundaries.py` — существующий control теперь явно создаёт acquisition receipt вместо доверия входящему trace. Прежние identity/score assertions сохранены, roster неизменен.
- `scripts/run_recovery_contract_gate.py` — один новый реальный fixture program `original_discovery_attribution`.
- `scripts/run_recovery_mutation_gate.py` — два адресных production defects, строгий baseline/roster/import/guard validator сохранён.

## Границы доверия

Ключ ledger связывает source, chunk index, SHA256 текущих body bytes, canonical reference identity/member binding/span, stable chunk ID, project identity, generation, source class, document path, scope/module и char span. Query traces и флаг `original_discovery` источника не входят в receipt. Ledger создаётся внутри текущего вызова, не принимается из публичного DTO/источника и не живёт между вызовами.

Каждый current independent query заново проходит body qualification со своими authoritative text/origin/relation и действующими source/lifecycle constraints. Фактически найденный exact window сохраняет acquisition score. Проверка другого направления через уже найденное тело получает нулевой search score; у original без реального receipt остаётся `admission_only=True`. Host lookup может иметь собственную квалификацию тела, но не передаёт credit родителю. Новый код не создаёт запросов, не меняет schedule/budgets и не расширяет lexical/semantic policy.

Unit variants намеренно остаются релевантными и original, и отдельному lookup: меняется только receipt binding. Они проверяют provenance, а не заменяют production immutable-source eligibility controls. Публичный program использует настоящий finite indexed member, source preparation, dispatcher, projector и snapshot validator.

## Реальный program и мутации

Один конечный каталог содержит `docs/storage.md` с тремя независимо написанными фактами. Program сначала требует исходный source fact и original coverage, затем те же bytes и все три query IDs после добавления двух lookup. Все варианты сохраняют `answer_supported=False`, `answer_available=False`, `edit_ready=False`, точный source path, неизменённый файл и валидный snapshot.

Третий вариант вызывает настоящий dispatcher, подтверждает наличие реальных original hits и удаляет только их из возвращаемого fixture result. Реальные lookup hits остаются, но получают враждебный metadata trace с ложным original credit. Public result обязан сохранить полезный source fact и два lookup IDs; original должен остаться missing, coverage — partial.

| Production mutation | Обязательный first failure |
| --- | --- |
| Следующий lookup снова демотирует все предыдущие traces | `retrieval_original_coverage_survives_lookups` |
| Lookup-only candidate может создать actual original credit | `retrieval_lookup_cannot_mint_original_discovery` |

Structured crashes, отсутствующий report, другой guard или негрин baseline не засчитываются как kills. Теперь полный recovery roster содержит 11 программ, mutation roster — 14 дефектов; существующие десять программ и двенадцать mutation contracts сохранены.

## Проверка и оставшийся риск

AST/compile всех шести Python files, JSON, два collection hashes, exact roster и все 14 уникальных anchors/изменённых AST проверены без импортов или исполнения project code. `git diff --check` пройден. Хеши и полный mutation crosswalk записаны в `query-discovery-ledger-static-audit.json`. Frozen TREASURE question/source и исходный корпус 100 вопросов неизменны.

Независимый review `agent_fixtures_impl` — **APPROVE для обычного PR CI**. Reviewer отдельно проверил actual dispatch → prepared window/member/generation → receipt → fresh qualification → final admission-only handling, оба intended first failures и отсутствие downstream восстановления поломанного guard. Его note: `original-discovery-independent-review.md`, аудит: `original-discovery-independent-static-audit.json`.

Реальный CI для новой версии ещё обязателен. Предыдущий recovery slice имел actual 10/10 PASS и 12/12 intended kills; эти результаты не доказывают новые 11/14. Здесь не заявляется исправление Russian original coverage floor, bare CamelCase relevance, sibling-subject borrowing или длинных multisection projection losses. Следующий анализ должен опираться на свежие same-call diagnostics и реальные видимые факты.
