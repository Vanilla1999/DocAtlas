# PR #211 — явный successor generated-consent tests

Дата: 2026-10-08. Автор: root. База:
`f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`.
Это отдельный узкий slice после первоначальной fixture migration. Он изменяет
ожидание прежнего traversal-контракта явно, а не объявляет все старые assertions
неизменёнными. Production source, retrieval и limits не меняются.

## Почему прежние 34 cases требовали отдельного решения

Первый [fixture review](PR211_DICTIONARY_FIXTURE_REVIEW_RU.md) оставил эти cases
красными: старые tests ожидали, что normal files останутся доступны, пока generated
files будут отдельно отфильтрованы без opt-in. Механическое добавление mixed
`code_files` не сохраняет этот premise: нынешний finite grant валидируется целиком
до первого source read. Вычислять разрешённый список из flag или actual rows
означало бы спрятать проверяемый guard в fixture.

Текущий контракт подтверждается `SourceBoundary.from_project`,
`iter_bounded_source_files`, `finite_local_path` и уже существующими tests в
`test_dictionary_exit_local_membership.py`:

- `test_invalid_literal_member_fails_whole_catalog`;
- `test_finite_membership_preserves_boundaries`;
- `test_generated_read_requires_literal_boolean_consent_and_finite_member`.

Finite membership и literal generated consent — независимые необходимые условия.
Вопрос, расширение/имя файла или truthy `1`/`"true"` не дают согласия. Если mixed
declaration содержит запрещённый member, preflight не выдаёт частичное разрешение
на normal member. Отдельная валидная normal-only declaration остаётся доступной.
Это соответствует ранее интегрированному
[local-membership contract](stage3/pr211-context-admission-checkpoint-2026-10-06/LOCAL_MEMBERSHIP_IMPLEMENTATION_RU.md).

## Реализованные две фазы

Каждый прежний parameter case выполняет **одни и те же два authored catalog**,
независимо от question, flag или результатов API:

1. Mixed declaration с normal и generated исходниками. При literal `True` каждый
   collector читает ровно эти файлы и возвращает их paths. При любом другом
   значении весь результат пустой и настоящий observer фиксирует **ноль source reads**.
2. Отдельная normal-only declaration, с теми же исходным question, requirements
   и flag. Normal source читается и присутствует в результате для каждого
   параметра. Существующие generated sources остаются unlisted и unread,
   в том числе при `True` и при явном generated path в вопросе/requirements.

В test scaffolding это две явно записанные декларации для разных controls,
а не runtime recovery, pruning denied members или автоматический повтор запроса
после отказа. Production fallback/retry не добавлен.

Observers вызывают исходный `Path.read_text`, возвращают его результат без подмены
и сохраняют SHA256 реально прочитанного UTF-8 текста. Expected hash вычислен из
созданных fixture bytes до установки observer. В первом module каждый reader
вызывается один раз; во втором фактически вызываются facts, repo-map и snippets,
поэтому expected read multiplicity равна трём для каждого разрешённого файла.
JSON catalog/config reads не считаются source reads. `.py`, `.dart` и `.go`
второго fixture находятся в действующем supported-extension set.

## Точный scope и сохранённые guards

| Test function | Сохранённые параметры | Concrete cases |
|---|---|---:|
| `test_generated_requires_boolean_true_even_for_explicit_path` | facts/snippets × None/False/1/`"true"`/True | 10 |
| `test_only_explicit_generated_opt_in_authorizes_source_scanning` | 8 исходных RU/EN/generated-path questions × None/False/True | 24 |

Все исходные questions, requirements, source contents, parameter values и
decorators сохранены. До изменения эти 34 cases были FAIL в df9; полный f0 CI
ещё ожидался при author review. Новый runtime outcome: **NOT RUN**.

В этих двух functions шесть прежних assertions получили восемь explicit
successor assertions. Старое предположение о normal subset внутри запрещённой
mixed declaration заменено whole-declaration denial и отдельным normal-only
positive. Это обоснованная test-contract migration, а не сохранение прежнего
partial-filtering поведения.

Остальные functions и их assertions не менялись, включая ранее reviewed 27 cases,
source scrubbing, CRLF bytes, cache isolation, gap semantics, technical boundaries
и два оставшихся recovery failures. Никакие corpus gold, ranking, admission,
qualification, output cap или CI gate не меняются. Новых/удалённых nodes,
skip/xfail и selector изменений нет; diagnostic hash roster прежний.

## Проверка автора и exact hashes

Stdlib AST сравнение с frozen f0: изменена ровно одна test function в каждом
module; test names/order/decorators прежние. Добавленные imports нужны для
observer; import/repository execution не выполнялись. AST parse/compile и
`git diff --check`: PASS. Pytest и реальные SDK/client sessions локально не запускались.

| Файл | SHA256 |
|---|---|
| `tests/test_dictionary_exit_local_residuals.py` | `3bf37fe379bae8767e664ad91e6fed48375a1c123ab0073ee6f13b5272e98181` |
| `tests/test_dictionary_exit_read_tails.py` | `e8c6761b947c23e5237dc7c709eb9ff33dccc521c93a2b61225e7de854a6dec7` |

Перед publication нужен независимый review; затем обычный CI на одном SHA должен
подтвердить both phases, конкретные path/read/hash checks и сохранение прежних PASS.
