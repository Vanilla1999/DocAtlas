# PR211: явная advanced surface для проверки patch completion

## Наблюдение CI136

Опубликованный HEAD `a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07`,
main CI `38026891736`, reader job `114141422568`.
Critical baseline содержит 61 testcase entry и один observed failure:
`test_real_service_retrieves_committed_fixture_member_bytes[none]`,
`critical_project_read_existing_retention_completion`.
Mutation credit не получен. Число skipped в этом summary не раскрыто,
поэтому остальные 60 entries не объявляются здесь PASS.

Exact critical XML: `docmancer-mutation-r4chxp6k/baseline.junit.xml`,
SHA-256 `c47207f5759dcf0c14bd2a806c52419162351920053031fb20e640608b1b9fd0`.
Сохранённый tail указывает на старую строку357
`project_read_presentation_controls.py`. Он не печатает весь failure DTO.
Предыдущие long-original и interrupted-acquisition guards исполнены до неё;
последний state receipt после неё не достигнут.

## Контракт установлен по source

`docmancer/mcp/_docs_server_shared.py`, blob `977e4d8838c8a933fed2e011401e45ffc8e7dade`,
строит validation schema из advertised schema. Поле `context_format`
добавляется только при `config.expose_advanced=True`.
Default surface этого поля не содержит. Это реальная optional advanced
публичная возможность, а не обязанность принимать поле в обычной surface.

`_docs_server_part01.py`, blob `9e6e57dfd786ad1665497524785db5fad093a439`,
проверяет эту schema **до** service resolution и вызова handler.
`context_tools.py`, blob `28fd767567e5c32124d84496a5937a87ee62164c`,
после принятого patch-format запроса требует
`_invoke_found_window_retention` и превращает отсутствие completion в
`unsupported_found_window_retention`.

Старый setup передавал patch format через ambient default surface и ожидал
ошибку более позднего completion boundary. Он не фиксировал exposure режима.
Исправление разделяет эти контракты и задаёт surface явно, независимо от env.

## Узкое изменение

На том же исходном question/lookups/project и том же сохранённом context
создаются два fixture-owned surface через штатный `build_docs_surface`:

1. `expose_admin=False, expose_advanced=False`: реальный
   `call_docs_tool_payload` обязан вернуть `validation_error`,
   без sources и без единого вызова подставленного project-context producer.
2. `expose_admin=False, expose_advanced=True`: тот же реальный
   `call_docs_tool_payload` проходит schema, один раз вызывает fake producer,
   затем обязан вернуть `unsupported_found_window_retention`, без sources.

Dispatcher запрещён на обеих операциях. Fake producer возвращает только
deepcopy уже полученного context; он не объявляет и не завершает completion.
Вызов внутреннего handler вместо публичного API не используется.
Production schema, exposed flags, service и completion protocol не меняются.

Сохранены все предыдущие 16 negative operations, включая прежний intended
completion guard; добавлена одна отдельно названная public-validation
операция. Healthy native read остаётся один, успешных dispatcher calls четыре;
две detached V2 projection replays и исходные 24 documents/queries неизменны.
Дополнительная работа: два in-memory surface construction и один отвергаемый
public call по сравнению со старым setup. Новых indexing/retrieval/native source
reads, pytest functions или mutation blocks нет.

Изменение final fixture tail не переносит исторический PASS на новый source.
Следующий совместный critical baseline и intended kills обязательны.

## Manifest

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `eval/agent_developer_v1/project_read_presentation_controls.py` | 100644 | `f133d9768ab498714bb48b4e3adea8076187e45a` | `a6cc45151a1b74ee5d45cddf5b2738dcb31c04ab` |
| `v2plan/PR211_PATCH_SURFACE_COMPLETION_RU.md` | 100644 | new | этот документ |

Proposed helper SHA-256: `85b92e56f35ca8c45e781d48d6f75e692ab7a22bd44f75715ab96f057470e638`.
Две обратные замены (один import и один final control block) восстанавливают
base побайтно. Helper имеет 457 physical lines; runner, selectors и case
counts неизменны. GitHub readback и independent source review требуются перед
интеграцией; локальное исполнение/pytest/imports не выполнялись.
