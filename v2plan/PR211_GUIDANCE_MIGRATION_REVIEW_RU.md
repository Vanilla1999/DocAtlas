# PR #211: миграция question/recovery guidance tests

Дата: 2026-10-08. Авторский rationale узкого test-only slice.

## Граница и основание

Исходная PR-база: `21fe472d983f394130849d6fd4e582043d58e9ba`.
Изменены только `tests/docs/test_agent_question_planning_contract.py`,
`tests/docs/test_agent_recovery_version_guidance.py` и этот документ.
Production, retrieval, frozen protocols/golds/ceilings, test markers и CI gates
в этом slice не менялись.

Исторический commit
`307c480cd7ffe2fff5a264167dcb09a7974ffc20` удалил policy heuristics и изменил
`agent_workflow_contract.py` / `templates/agent_contract.md`. Основание изложено
в `stage3/pr211-context-admission-checkpoint-2026-10-06/CORPUS_POLICY_DICTIONARY_EXIT_RU.md`
и `DELIVERED_SURFACES_DICTIONARY_EXIT_RU.md` в том же каталоге: не выводить из
естественного языка переводы, переписывания, подзадачи, имена источников и
предполагаемые ответы; сохранять исходный вопрос и явные lookup inputs.

Commit `5feb94fd7cce23ae0c68ba4711a4b394817ff4f6` затем сократил основной
installed guide и вынес подробности в доступные по ссылкам optional references.
Требования `CURRENT_WAVE_DECISIONS_RU.md`, пункты 4–5, сохраняют короткий
default MCP interface, необязательность предварительного skill read и
доступность подробных guides в установленном skill.

На самой базе `21fe472d` machine contract уже содержит:

- `explicit_lookup_queries_only=True`, `maximum_lookup_queries=5`,
  `original_question_unchanged=True` и `inferred_semantic_equivalence=False`;
- отдельные calls для независимых вопросов; явные lookups уточняют тот же вопрос;
- `gap_resolution.continuation_requires=explicit_lookup_or_issued_bounded_source_read`,
  immutable root question, `inferred_subquestions=False` и неизменные scope/budgets;
- `retry_after_prepare_requires=terminal_success`, возврат к неизменному вопросу,
  polling только возвращённого `job_id`, отсутствие автоматического retry failure;
- текущее project version binding, explicit exact/historical version только по
  запросу и повторный query после изменения lockfile;
- отсутствие answer/edit authority у retrieval context и автоматического
  разрешения на редактирование при `hard_stop=false`.

Старые ожидания `recommended_lookup_query_min=1`, `max=3`,
`decomposition_triggers`, `cross-language-single-question` и автоматического
gap splitting расходились с этой базой. Их восстановление изменило бы текущий
продуктовый контракт. Отдельно текущий footprint slice переносит guidance из
описаний дочерних полей в описание advertised tool; сами input constraints
остаются проверяемыми независимо от места пояснений.

## Что проверяется теперь

Имена всех восьми planning nodes и трёх recovery nodes сохранены, включая
исторические имена с `decomposition`. Имена служат совместимости diagnostic
inventory и не объявляют удалённое поведение действующим.

| Группа существующих nodes | Положительный контроль | Отрицательный контроль |
|---|---|---|
| Runtime question guidance | Реальный `runtime_public_tool_dicts()` и shared `assert_public_context_guidance`; исходный вопрос, одна конкретная задача, явные same-question lookups, literals, scope и отсутствие authority | Удаление unchanged/explicit-only/no-batching/meta-question запретов из actual descriptions должно разрушить проверку, независимо от глубины описания |
| Machine lookup policy и example | Сохранены grouping flags и конкретный явно переданный русский lookup `актуальность индекса`; он валидируется advertised schema | Нет старого авто-переводного example; flips original/conditions/grouping/expected-answer/source-name/authority и восстановление decomposition triggers отвергаются |
| Lookup bounds | Omitted, null, empty, один и пять явно переданных lookups допускаются действующим schema; min/max длины и uniqueness сохраняются | Шесть, дубликаты, пустая/слишком длинная строка и неверный тип отвергаются; пустой original question отвергается |
| Canonical и rendered guidance | Исходный вопрос; identifiers, versions, conditions, negation, comparison sides; максимум пять explicit lookups; никакого обязательного skill-first | Удаление explicit-only, negation или запрета invented translations/rewrites/subquestions отвергается |
| Gap policy | Только explicit lookup или issued bounded source read; root immutable; scope/budgets неизменны; unverified flags не требуют чтения сами по себе; нет edit grant | Auto-subquestions, targeted auto-query, scope/budget reset, forced read, повтор span, edit grant и mandatory skill read отвергаются |
| Short skill + detailed reference | Root и canonical short instructions проверяются отдельно; проверяются конкретные ссылки и реальное содержимое packaged troubleshooting guide; quickstart имеет собственные continuation guards | Удаление issued/bounded read, запрета auto-executed diagnostic rephrases или запрета повторного span отвергается |
| Installed recovery/version | Все прежние положительные assertions сохранены; реальный optional prepare guide дополняет terminal success / not running, failed, cancelled / current version / lockfile checks | Ready после failed/cancelled/running, auto retry и reuse previous version отвергаются |
| Machine recovery/version | Прежние terminal-success, returned-job, no-failure-retry, current binding, previous-version-is-not-current и condition preservation assertions сохранены и дополнены | Flips retry gate, question rewrite, speculative preparation, discovery, stale version и `hard_stop=false` permission отвергаются |
| Advertised recovery/version | Shared context/lifecycle meaning helpers читают actual tool descriptions; `version` остаётся optional string/null | Удаление success/readiness, confirmation/network consent, current-version/requery правил или returned-job/no-discovery ограничений отвергается |

Подробный guide проверяет source URI как возвращённую capability с host reader
support, а paths/hashes/spans — как attribution; запрещает конструировать URI,
повторять span, сбрасывать budgets переименованием вопроса или заменять denied,
expired/changed source другим либо latest file. Проверка не предполагает, что
основной короткий skill уже содержит весь текст optional guide или что guide
загружен автоматически.

Структурная валидность lookup input не доказывает его семантическую
эквивалентность исходному вопросу. Этот slice проверяет текущие instructions,
machine policy, examples и schema; живой reader/model benchmark им не заменяется.

## Проверка и её пределы

- `git diff --check` для owned files: PASS.
- Stdlib `ast.parse` обоих modules: PASS.
- AST roster: восемь planning и три recovery nodes, без новых decorators или
  parametrizations. SHA-256 roster совпадает с существующими manifests:
  planning `82044bd7d9b1a3c5c8592ab1e469b468ad86531b7298ada5bc5e6beac8a65a24`,
  recovery `74615c98b2d3954417eeeda0689fec106caf6fe1ada684e14002d671467e61b4`.
  Diagnostic manifests не изменялись.
- Из AST извлечены только чистые assertion helpers; проверены literal constants
  current tool descriptions/schema и workflow, а также bytes исходных templates.
  Девять положительных и 49 отрицательных helper controls: PASS. Это static
  data-adapter проверка. Она не выполняет repository imports, renderer,
  `jsonschema`, pytest, MCP/server, Git fixture subprocesses или network/provider.
- Реальные pytest nodes, runtime schema validation и установленный renderer:
  NOT RUN локально — среда без pytest/MCP/dependency runtime. Отсутствие такого
  прогона не скрывается static helper результатом.
- Независимый review хранится отдельно в
  `PR211_GUIDANCE_INDEPENDENT_REVIEW_RU.md`; его verdict и exact reviewed hashes
  должны предшествовать публикации slice.

Команда для подготовленной offline CI-среды после публикации общего SHA:

```sh
pytest -q tests/docs/test_agent_question_planning_contract.py tests/docs/test_agent_recovery_version_guidance.py
```

Затем нужен общий acceptance на конечном SHA согласно
`PR211_CI_BASELINE_AUDIT_RU.md`: required core/advanced/downstream/release и
installed/client проверки. Этот slice не закрывает advanced legacy v3/edit
expectations и не меняет frozen retrieval 800-token gate. Успешная миграция
guidance сама по себе не означает, что PR #211 готов к merge.
