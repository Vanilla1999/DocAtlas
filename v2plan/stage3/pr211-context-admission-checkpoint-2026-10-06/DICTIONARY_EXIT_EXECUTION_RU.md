# Dictionary exit: изменение приоритета владельцем

Latest handoff, next bounded slice и current file map:
[CONTINUE_HERE_RU.md](CONTINUE_HERE_RU.md).

Дата: 2026-10-06. **ACTIVE, не DONE.**

Владелец разрешил сначала удалить ручные смысловые механизмы и отвязать
потребителей, а затем улучшать качество общими механизмами. Доказанная замена
aliases и сохранение прежней полноты больше не являются предварительным
условием удаления. Прежние результаты и критерии не переписываются задним числом.

## Контракт выполнения

- Только исходный вопрос и явно переданные lookups в существующих пределах.
- Нет генерации тематических aliases, ожидаемых команд/API/ответов,
  смысловой эквивалентности lookups исходному вопросу и тематических boosts.
- Scope, project/library/version identity, freshness, hashes, spans, provenance,
  network/consent boundaries и существующие search/output budgets сохраняются.
- Цитата сама по себе не подтверждает ответ, полноту или разрешение редактировать.
  Удаление смыслового proof не заменяется безусловным положительным решением.
- Существующие tests/gold/release thresholds и замороженные 224 случая не меняются.
  Recall failures фиксируются отдельно от технических/safety failures.
- Новые словари в prompt/config/другом модуле не являются выполнением задачи.

## Организация

Перед запуском прочитаны существующий inventory и карты selector/attribution.
Два исполнителя работают в отдельных detached worktrees на `9a7299e2`:

- `/tmp/opencode/dictionary-exit-retrieval`: query planning, retrieval/ranking;
  локальный исходный `project_retrieval_intent.py` скопирован без reset.
- `/tmp/opencode/dictionary-exit-admission`: остальные domain/application consumers,
  смысловые requirements/admission/proof и context-only путь.
- Независимый проверяющий: read-only аудит защит и последующая проверка интеграции.

Граница владения файлами явно задана исполнителям. DTO/signatures сохраняются
для интеграции; смысловые таблицы удаляются, а не прячутся за выключенным flag.
Интегратор применяет и проверяет изменения последовательно, без уничтожения
первоначальных локальных правок. Полное отсутствие словарей не заявляется, пока
не проверены оставшиеся live paths и инвентарь REMOVE/SPLIT/REVIEW.

Результаты реализации и проверок будут добавлены после возвращения исполнителей.

## Исходный независимый аудит

Проверяющий выполнил bounded исходные suites: 234 passed, 1 failed.
Исходный failure:
`tests/docs/test_context_projection_boundaries.py::test_frozen_request_flow_prefers_project_context_module_witnesses`
— отсутствует visible witness для frozen `flow_mcp`; это полнота, не green gate.
13 frozen hash entries совпали, 224 случая не изменены; 159 ledger rows сохраняют
`NO_CHANGE_NOT_AUTHORIZED`. Это результаты до применения двух executor patches.

## Отдельный integrator slice: source navigation

В `docmancer/docs/code_context.py` удалены `_LOW_SIGNAL_TERMS`,
`_GENERIC_SOURCE_TERMS` и product substitution `browser/tsd → tsd_browser`.
Оставлены literal tokens/identifiers, явные entry symbols/changed paths и прежние
term/file/hop/line bounds. Три новых behavioral checks прошли.
Первый запуск остановлен существующим fail-closed diagnostic inventory:
новый модуль ещё не был зарегистрирован. Добавлен отдельный hash-bound manifest
только для нового модуля; старые labels/tests/hashes не менялись. Повтор: 3 passed.

## Открытая область вне двух executor slices

Connector corpus policy (`filtering.py`, `github.py`) всё ещё содержит default
topic/locale exclusions и docs-root inference. Не объявляется техническим
исключением или завершённой миграцией; изменение ingest scope требует отдельно
проверить explicit URL/root/network boundaries. Protocol tool enums, явные
identity→URL mappings и примеры использования сами по себе не query dictionaries.
Окончательный remaining inventory обязателен после интеграции.

## Admission patch интегрирован (retrieval ещё pending)

Применён `/tmp/opencode/dictionary-exit-admission.patch`, 18 production files:
убраны answer/API generators, semantic admission/facet proof и часть
subject/attribute aliases. Полный список и честный remaining ledger:
`docmancer/docs/application/DICTIONARY_EXIT_INTEGRATION.md`.
Добавлен новый hash-bound diagnostic shard только для новых admission tests.
Штатная collection с network guard: admission + code_context **32 passed**;
`git diff --check` passed. `--noconftest` результат исполнителя не подменяет их.

10 bounded technical/mixed suites после admission patch: **140 passed, 7 failed**.
Команда: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest
-p no:cacheprovider -q` плюс следующие файлы:

```
tests/docs/test_mcp_docs_tools_registration.py
tests/docs/test_finalized_mcp_output_integrity.py
tests/docs/test_mcp_boundary.py
tests/docs/test_target_security.py
tests/docs/test_content_trust.py
tests/docs/test_review_source_capabilities.py
tests/docs/test_reference_hash_domains.py
tests/docs/test_review_assignment_identity.py
tests/test_source_search_edit_readiness.py
tests/test_source_isolation_regression.py
```

Все 7 failures — positive `answer_supported` expectations в Python zlib cases
последнего файла (exact-source positive, три semantic-list paraphrases и три
delimiter-control baseline positives). Это потеря прежней answer certification,
не PASS и не автоматическое разрешение менять assertions. Остальные перечисленные
технические/safety suites прошли. Combined retrieval patch и final MCP path ещё
не проверены; независимый diff review admission запущен отдельно.

## Retrieval patch интегрирован

Применён `/tmp/opencode/dictionary-exit-retrieval.patch`. Единственный конфликт
касается исходного локального удаления `instruction_trust` block: общий patch
применён без этого файла, его интерфейсы перенесены отдельно после проверки
исходного diff. Этот блок не восстановлен; unrelated user changes не сброшены.

Убраны generated aliases/probes/rewrites, topical/library boosts, synonyms,
NL tool routing и исполнение regex routers. `QueryRouter` остался совместимым DTO,
но больше не выбирает filters по вопросу. Новый plan содержит исходные bytes
вопроса и до пяти независимых explicit lookups; path остаётся явным scope metadata.
После добавления отдельного нового diagnostic shard: retrieval/admission/
code_context штатная collection **54 passed**.

Независимый review не обнаружил продемонстрированный bypass technical/safety
границ, но нашёл integration defects: selected library quotes исчезают при
insufficient support, supplied old canonical decisions обходят новую context-only
политику, anonymous/mislabeled traces могут получать coverage. Эти defects не
принимаются как просто потеря полноты. Executor admission исправляет common
projection и authoritative crop attribution; executor retrieval убирает remaining
default read-path topical/dependency/task triggers в отдельных owned files.
Final combined MCP validation ещё pending.

## Read-routing и completeness follow-up

Executor retrieval убрал default read topical dependency aliases, query-based
low-trust exemptions, NL patch inference, semantic request-part scoring/stopping
и snippet fallback queries. Новый routing module: 20 passed штатно. Его unchanged
bounded facade/network run: 93 passed, 24 failed, log
`/tmp/opencode/dictionary-exit-read-routing-service-tests.log`.

Integrator убрал story/layer/RU-action completeness таблицы и эвристическое
`edit_ready` из `answer_completeness.py`. Остаются bounded literal relevance terms
и context-availability diagnostics без completeness/proof authority. Из `quality.py`
убраны known-command list, prose-noise list и implementation-location NL triggers;
code/fence/table/path syntax сохранён. Эти изменения ещё требуют final review.

Промежуточный combined new-test run: 78 passed, 1 failed. Новый admission test
ожидал coverage anonymous `lookup-1`; ongoing authoritative-lane fix больше не
допускает этот ID. Это mismatch новых integration tests, не разрешение ослабить
старые тесты. После завершения producer/consumer contract он должен быть исправлен
с настоящим request-plan provenance и перепроверен штатно.

Два isolated worktrees занимают 117 MiB + 116 MiB (наблюдение `du -sh`, не полное
resource SLA). Final public mutation-inference и partial-projection fixes выполняются
раздельно. Corpus pins по-прежнему 13/13; tracked tests/eval/workflows diff пуст.

## Public mutation inference follow-up

Public handler больше не выводит/передаёт mutation contract или patch_context
из NL question. Neutral mutation builders и action-packet fallback не превращают
required paths в `modify`. Explicit SDK contracts сохраняют отдельные target/
readiness gates. Public partial-recovery layer сохраняет sources/snapshot до
budget/transport validation, вместо silent discard.

Новые public tests: 19 passed, вместе с read-routing 39 passed. Unchanged bounded
legacy suite: 49 passed, 49 failed, log
`/tmp/opencode/dictionary-exit-public-request-legacy-tests.log`.
Failures не разрешают менять old assertions. Наблюдён integration mismatch:
transport validator пока rejects insufficient+retrieval_only; repair projection
исполнителем B ещё выполняется. Legacy patch-plan/proof parsers за explicit SDK
request_plan остаются OPEN. Отсутствие NL inference не равно полному удалению
всех historical parser dictionaries.

## Итог интегрированного среза

**Implemented partial dictionary exit; полный milestone ACTIVE / NOT DONE.**
В primary объединены retrieval, admission, read-routing и public-request правки.
Новые tests теперь проверяются штатным conftest с отдельными new-only diagnostic
shards. Финальный combined run восьми `test_dictionary_exit_*.py`: **146 passed**.
Existing tracked tests/eval/workflows не изменены. Frozen corpus: **13/13 hash
pins совпали, 224 случая не переписаны**. Commit/push/merge не выполнялись.

Реальный stdio smoke `scripts/docs_mcp_stdio_smoke.py` на current source path:
**PASS**, включая lifecycle consent/guard/status и text fallback. Это local
installed entrypoint с `PYTHONPATH` primary, не rebuilt-wheel release acceptance.
Два новых indexed-MCP tests проходят с actual sync и public handler, без retrieval
mocks. Найденный blanket `unclassified_source` отказ исправлен: ordinary docs
authority остаётся unknown, genuine risk flags не игнорируются.

Independent review обнаруживал technical bypasses при context-only materialization;
исправлены обе ветви docs_answer/docs_context и свежие/старые supplied decisions:
current question/identifier/public-requirement input limits и mandatory exact snapshot.
В последнем независимом review **15 snapshot checks + 7 limit checks passed**;
дано **scoped technical approval**, не approval полного dictionary exit/релиза.

## Честная красная quality gate

`archives/dictionary-exit-self-host-v1.json`: unchanged self-host gate **FAIL**.
Запуск сделан после source-risk correction, перед последними input-limit/snapshot
поправками; это сохранённый diagnostic срез, не final green acceptance.
15 cases: useful 11/15, top3 relevant 12/15; обязательные факты/paths/attribution
дают failures в случаях 01/08/12/14/15. Frozen quality thresholds не менялись.
False-supported=0, source/token budget violations=0, packs/history contamination=0;
max sources=2, estimated tokens=653 в этом конкретном прогоне.
Original coverage count=0; это открытая attribution/quality regression, не исправлено
и не переклассифицировано в PASS только потому, что support flags false.

## Remaining OPEN после независимого review

- **Default read:** `query_reference_binding.py` relation/role/source-language tables;
  `context_candidate_ranking.py` reporting/proof/comparison priorities;
  `_answer_units_shared.py`/`_answer_units_part01.py` proposition vocabulary;
  path-based corpus classification в `project_doc_ranking.py`.
- **Explicit SDK/advanced patch:** legacy behavioral/policy/typed proof, premise/
  governance/frame parsers, patch constraints/review `PHRASE_ALIASES` и inline
  aliases/keyword rules; source-map stopword lists.
- **Corpus/config/prompts:** connector root/locale/blocklist/query-parameter tables,
  GitHub exclusions; discovery registries и delivered scope/decomposition policy
  требуют поэлементной классификации. Protocol/schema mappings не удаляются лишь
  потому, что представлены таблицей.

Следующая реализация — оставшиеся live read rules, затем explicit SDK/patch и corpus
policy с тем же разделением технических guards и смысловых предположений. Поиск
новой модели не является предварительным условием удаления этих правил.
