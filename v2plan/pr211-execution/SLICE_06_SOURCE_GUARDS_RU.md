# PR211 — current source guards вместо 61 связанных setup ERROR

Base: `bfe9709160f4730d51311847ca9e0c5b2ab460a3` (baseline failures взяты из `11489239ae0a5ff85c1f817f0650bea661e88ba1`, core Python 3.12 run `37955085277`). Статический slice; repository runtime не исполнялся.

## Что действительно ломалось

| Test root | Setup ERROR | Первая причина |
|---|---:|---|
| `test_context_completion_guards.py` | 24 | Original `typer-05` доходит до empty retrieval и не вызывает projector. Сам fixture дополнительно требовал removed generated `retrieval_hint` как источник inspection permission. |
| `test_query_block_guards.py` | 23 | Исходный RU CORS вопрос не дал projector inputs. Guard tests зависели от этого retrieval result. |
| `test_admission_pipeline_invariants.py` | 10 | Shared capture требовал projection attempts, затем tests ожидали отсутствующий `query-need-1` и inferred `typed_local`. |
| `test_evidence_set_source_preparation.py` | 4 | Тот же shared capture; positive ожидал inferred `cause` edge по двум предложениям, тогда как source graph сейчас строит только Markdown heading/list/table edges. |

Это не 61 независимый дефект member storage. Fixtures уже использовали confirmed `index_project`; исходные вопросы не доставляли нужный source seed.

## Новый fixture contract

`_current_source_guard_fixtures.py` принимает только явный finite authored `documents` map, вызывает существующие `write_project` + `isolated_service` + `index_project`, затем настоящий public `call_docs_tool_payload` через observational capture. Production consent, member transaction и source preparation не заменяются.

Positive fixture сохраняет исходный question и scope. Дополнительный lookup — явный evaluator input, сохранённый в request, а не тайная server rewrite. Source seed обязан иметь реально доставленный полный authored fact, точный source path, исходные байты в указанных line coordinates и current model-visible validation. `source_binding` возвращает только snapshot реально наблюдавшейся public projection, не реконструирует доверенные поля.

`canonical_range` отдельно проверяет конкретный текущий компонент: на реальном source binding вызывает `_verified_document`, Markdown parent parser и `_context_row`. Это source-range unit input, не выдаваемый за дополнительный public response. Ни `qualified=True`, ни source hashes/member grants не фабрикуются для positive.

## Контрактный crosswalk

| Старое ожидание | Текущий обязательный контроль |
|---|---|
| Original prose порождает `query-need-1` с typed relation | Авторизованный test lookup имеет `query-lookup-1`, `origin=host_lookup`, без parent credit. Semantic witness/need claims отсутствуют. Полный `RelayClient ... 7 seconds` факт проверяется независимо по source bytes. |
| Обрезанный default witness обязан провалить inferred predicate parser | Source crop не сохраняет typed witness/need claims и не проходит полный authored fact oracle. Обычный lexical partial match не превращается в ответ. Source switch/snapshot/version/path/freshness отказы и no-I/O остаются. |
| `This rule prevents ...` автоматически создаёт cause edge | Реальные source structures имеют heading/list/table edges; original why-contract остаётся unresolved. Raw snapshot/source identity/window proposals/replay/no reread и отсутствие private data/answer authority проверяются как прежде. |
| Empty original question получает inspection через автоматически созданный hint | Исходный plan содержит только original; отсутствие current hint authority не разрешает новое чтение. Injected `retrieval_hint` + forged qualified metadata также не выдаёт permission. |
| Query-block positive требует непредсказуемой стадии original retrieval | Истинный public original+lookup даёт prepared source, а canonical expansion/fidelity/source forgery/forbidden-term guards проверяются напрямую на нём. |
| Удалить host lookup из plan, чтобы оживить старый supplement/recovery | Запрещено. В обоих files есть отдельный no-op контроль на фактическом host-lookup plan. |
| Два набора почти одинаковых project/generation/version/hash/path/stale/lifecycle/raw/scope forgeries | Current source-forgery matrix сосредоточена в query-block family; completion сохраняет специфические forged hint/no permission/inspection range controls. Каждый canonical positive проверяется до negative mutation. |
| `risk_flags=['untrusted_instruction']` само по себе запрещает source quote | Это больше не текущий source policy input: `_verified_document`, current reference binder и policy qualifier такого поля не интерпретируют. Metadata flag не становится source/answer/edit authorization. Inactive metadata filter assertion снят; реальные source identity/hash/freshness/lifecycle и read-only constraints остаются. |
| Fixed output limits 800/300 и compatibility `max_tokens=0/1` | Убраны из мигрируемых controls. Source fidelity, scope, current DTO и operational bounds сохраняются; новый helper вызывает validator с `max_tokens=None`. |

## Original-only продуктовые regressions не спрятаны

Четыре отдельные обязательные tests вызывают original question без lookup:

1. Точный исходный `RelayClient` вопрос → полный `default timeout is 7 seconds`.
2. Точный исходный `OrbitResolver` вопрос → оба исходных предложения, без inferred cause certification.
3. `Из каких компонентов состоит origin в CORS?`, исходный `scope=all` → полный исходный protocol/domain/port fact со всеми примерами.
4. Точный frozen `typer-05`, исходный `scope=all` → оба исходных предложения с preceding space и точным `" /-S"` versus `"/-S"`.

Если original-only retrieval остаётся плохим, это FAIL, не skip/xfail и не автоматическое изменение ожидания. Explicit-lookup fixture также обязан доставить authored facts; его ошибка честно оставляет boundary family красной. Успех этого slice ещё не подтверждён runtime.

## Сохранённые границы

- Frozen original source documents, question strings и scope не менялись. Four mandatory original-only regressions отделены от source-bound controls.
- Не менялись production files, global capture/reference helpers, public schemas или shared runtime/index helper.
- Source snapshot maximum 262144 chars, block inventory 256, parser/work bounds, resource `SourceContinuationReader.max_lines` и member consent не отменены.
- I/O guards по-прежнему запрещают file reads/resource issue во время source-range trials; recorder в source preparation вызывает настоящий метод без замены результата.
- Existing bridge spy сохраняет настоящий `_context_row` (`wraps`), и проверяет отсутствие создания кандидата через intervening prose.

## Файлы и статика

- Новый `tests/docs/_current_source_guard_fixtures.py`.
- Четыре test roots из таблицы.
- Ровно четыре собственных diagnostic shards: `admission_contract`, `evidence_sets`, `query_blocks`, `completion_guards`. Hash считается по исходным base node IDs, как в `tests/diagnostic_labels.py`, без runtime collection.
- AST пяти Python files, JSON четырёх shards, node-hash coverage и `git diff --check` — PASS.
- Test function count: 34 → 38; parametrized invocations: 86 → 75. Четыре original-only product controls и независимые evaluator/no-work controls добавлены при удалении дублированных/retired assertions; это не runtime PASS и не зачёт количества checks через упаковку цикла.

## Что проверить в CI/review

1. Public original+lookup positives действительно дают bound facts/current DTO; не подменять missing source artificial trust snapshot.
2. All seven current source metadata forgeries и five reference mutations должны отклоняться при non-vacuous canonical positive.
3. Lookup qualified IDs не приписываются original и не создают typed semantic witness.
4. Canonical CORS bridge и Typer range остаются точными bytes/ranges, не пропускают intervening prose и не регистрируют resource во время trial.
5. Four original-only regressions либо зелёные, либо явно показывают оставшийся product retrieval loss. Они не должны блокировать collection/setup других independent guards только из-за своего результата.

## Ещё не выполнено этим slice

71 direct project mutation без explicit member grant, прочие ~1900 core failures, advanced98, broader ordinary-test reduction и installed/client acceptance не исправлялись. Полная family classification начиналась read-only и будет продолжена отдельно; данная таблица строго относится к 61 baseline setup ERROR.

## Review corrections

Independent reviewer нашёл и исправлены два gaps: source_binding теперь сравнивает все final visible fields с конкретным observed row и snapshot.projected_source (исключён только поздно зарегистрированный source_uri); same-fact/path с изменёнными hash/coordinates отклоняется отдельными controls. Checked/empty/answer early-return guards сохранены на явно отдельном original-only unit input с assertion sentinel запрета source work, без редактирования captured host request. Root дополнительно потребовал реальный crop oracle: общий source_contains_fact применяется к actual _requalify_visible_source returned row (positive перед negatives), а не к константе входного snippet. No typed/need/parent/answer/edit claims также проверяются. AST5, shard hashes4 и diff-check повторно прошли; runtime не запускался.

## Review result

Independent source review: APPROVE for PR CI. Root and reviewer corrections preserve final delivered-row binding, shared fact oracle on actual requalification result, and separate checked/empty/answer no-op controls. Runtime remains NOT RUN for this slice.
