# P0: interfaces — поэлементная классификация

2026-10-06, second pass. Audit/source mechanism decisions завершены;
продуктовое техническое сохранение **не утверждено**. Product,
tests, gold, общие checkpoint-артефакты не изменены. AGENTS.md в рабочем
дереве и проверенных родительских каталогах не найден.

## Покрытие и результат

Вход: `archives/p0-agent-input-interfaces.json.gz`.
Выход: `archives/p0-agent-interfaces-decisions.json`.

| Метрика | Число |
|---|---:|
| Входные/выходные owner units, взаимно однозначно | 248 / 248 |
| Уникальные исходные файлы | 45 |
| Scan nodes, сохранённые в `node_ids` | 1454 |
| REMOVE | 0 |
| SPLIT | 30 |
| TECHNICAL-RETAIN-CANDIDATE | 218 |
| OPEN | 0 |

Reachability: `default` — 198; `static-edge-only` — 34; `SDK` — 12;
`fallback` — 4; `unresolved` — 0. Это **статически прослеженные** маршруты,
не утверждение о запуске всех ветвей в baseline. `default` для packs-serve
означает обычный путь именно этого интерфейса, не вызов из docs-serve.
Hybrid semantic search — отдельная opt-in ветвь, не lexical fallback.

Каждая строка содержит исходный SHA256, owner/source anchor, решение,
конкретные named consumer references, сохраняемые ограничения, reachability,
limitations, исходные node ids и unresolved expressions из входа. Прочитаны
actual AST owners: тела функций/методов, значения assignment owners и
существенные регистрации, bridges, templates и вызываемые policy builders.
Решение распространяется на owner, поэтому смешанный owner помечен SPLIT,
даже если отдельный scan node — обычный JSON key.

Для девяти second-pass owners добавлены `consumer_boundary_refs`: это
конкретные проверенные регистрации, handlers, config/transport boundaries,
а **не выдуманные positive consumers**. У шести definition-only helpers
`consumers=[]` сохранён честно. Их `static-edge-only` означает классифицированный
inspectable механизм без найденного named caller; не dead-code/remove approval.
Source-level technical DTO classification не требует доказательства всех
возможных dynamic/external imports и не требует P1 approval.

SHA256 текущих bytes всех 45 файлов сверены с каждым из 248 input units.
Проверены отсутствие пропусков/дубликатов `(path, owner)`, сохранение всех
`node_ids`, допустимые decision/reachability и существование файлов/строк
consumer references. Это не проверка релевантности или доказательство
семантической достаточности. Продуктовые тесты не запускались и не менялись.

## D10: фактический default и fallback

`mcp/serve.py:31-44` регистрирует meta-tool handler; поиск проходит через
`Dispatcher.search_tools` → `search_with_metadata` → `_lexical_search` →
`_tokens(query, expand=True)` → `_SYNONYMS` (`mcp/search.py:141-165`).
Hardcoded create/open/add/new, issue/ticket/bug, delete/remove/destroy,
list/search/find **меняют поисковый запрос**. Это не token grammar.

SPLIT: `_lexical_search`, `search_with_metadata`, `Dispatcher.search_tools`.
Сохранить corpus-derived BM25, package filter, limit, RRF и lowConfidence;
семантическую таблицу не считать техническим исключением. Ни таблица, ни
`_tokens` не входят в этот partition input, поэтому им не добавлены новые
выходные rows; зависимость явно записана у потребителей.

При `DOCATLAS_MCP_SEARCH=hybrid` lexical lane всё равно выполняется первой;
`SemanticUnavailable` возвращает тот же dictionary-dependent lexical result.
Пустой query при конкретном package — отдельно помеченный package-list
fallback, не словарная замена вопроса.

`_operation_search_text` — SPLIT boundary: внешние aliases/intents/tags,
example queries и schema prose становятся retrieval data. Это не повод
удалить все внешние описания как product dictionary, но и не разрешение
превращать их в execution policy/expected answer. `_schema_terms.walk`,
camel-case/ASCII token boundaries и числовой `_merge_hits` предложены как
technical candidates отдельно; ASCII recall limitation сохранена.

## D33: инструкции отдельно от serialization

SPLIT у `RAW_TOOLS`, public advertised descriptions/input schemas,
`_tool_spec`, resources/templates, `read_docs_resource`,
`public_agent_contract`, `_get_template_content`, `_build_skill_content`,
`install_cmd`, `agent_contract_cmd`, legacy `_agent_instruction`.

Actual `WORKFLOW_POLICY` содержит NL category→scope и обязательные
`decomposition_triggers`; `PUBLIC_EXAMPLES` — иллюстрации, не runtime
question→expected-answer lookup. Hash identity не делает policy технической.
Прочитаны `templates/agent_contract.md`, `skill.md`, `project_bootstrap.md`:
placeholder rendering технический, доставляемое scope/lookup/pre-edit
руководство — отдельная политика. CLI `agent-contract` использует другой
builder, `docs/agent_contract.py`: actual tool_selection/evidence_rules и
Markdown guidance также классифицированы как D33 SPLIT.

Не предлагается ослаблять неизменность root question, exact scope,
confirmation, untrusted document boundaries, конечные budgets или citation
integrity. Существующее несовпадение generated resource workflow с public
schema (`mode`, `ecosystem`) не исправлено и не превращено в право расширить
public interface. Source resource reference не является edit authority.

Agent config serialization (`known_agents`, styles, command/args ownership,
JSON/TOML mapping) — отдельные technical candidates. Это точные host ids,
не NL task router. Конфликтующие чужие MCP entries и пользовательские
instructions должны сохраняться. Реальные внешние user configs не читались.

## D34: внешние данные не дают привилегий

`registry._derive_safety` (`registry.py:594-607`) снимает destructive flag с
POST/PUT/PATCH/DELETE, если path содержит `/search`, `/query`, `/list`, `/find`.
Это смысловое path→authorization исключение, а не HTTP serialization.
SPLIT также у `compile_openapi`, `build_openapi_pack`,
`KnownOpenAPIRegistry._build_open_meteo`, `install_package`,
`Dispatcher.call_tool`: прослежено распространение safety metadata до gates.
Замена не реализована; нельзя считать текущие metadata доказанной безопасностью.

Сохраняемые guards: explicit execute/destructive opt-ins, operation grants,
schema validation, credentials, host/scheme/private-network checks, DNS
stability, bounded response, redirect non-following в HTTP executor,
module/environment/venv ограничения Python executor и path traversal rejection.
`NETWORK_MODULE_ROOTS` — capability deny-list candidate, **не полная sandbox**.
`_infer_allowed_domains`/`_bounded_inspection_target` производят proposed scope,
не доверие к источнику и не network approval.

Second pass: `HostedRegistry.fetch` — TECHNICAL-RETAIN-CANDIDATE для точных
artifact/protocol fields и optional SHA refusal; `compile_pack_from_url` —
SPLIT по доказанной цепочке compiler → `_derive_safety`, не по неизвестности
внешнего fetch boundary. Оба fetch следуют redirects; отсутствующие
host/private-IP/response-byte guards записаны как конкретные policy risks.
SHA verification и OpenAPI grammar не закрывают эти риски, но отсутствие
security certification больше не смешивается с неизвестностью механизма.

## Named routes, bridges и недостижимые поверхности

- `cli/__main__.py:74-97` явно регистрирует CLI callbacks. `cli/commands.py`
  реэкспортирует shards, синхронизирует overrides перед Click callbacks.
  `commands.py:17` заменяет старый `_commands_part04.clear_index_cmd` на
  `state_commands.clear_index_cmd`: старый owner — static-only, focused owner
  — public default. Не объявлены оба callbacks live по одному имени.
- `build_docs_surface` (`_docs_server_shared.py:105-119`) фильтрует admin и
  advanced через явные config flags. `_handler_for_tool` выбирает точные
  tool ids; `call_docs_tool_payload` проверяет advertised schema, unknown
  fields и project-owned destructive scope **до** service routing/handler.
- Default: `get_docs_context` → `handle_context_tool`; `prepare_docs` и
  `docs_status` → `handle_prefetch_tool`. Library/project legacy handlers
  содержат ветви, исключённые финальным `RAW_TOOLS` filter. Наличие строки
  в handler не делает её публично вызываемой. Admin/advanced — opt-in
  static edges, не default content route.
- `maintenance` branch direct handler существует, но public advertised
  schema не допускает это поле. Его reachability не объявлена default.
- Terminal `compact_mcp_payload` не режет finalized canonical projections:
  over-cap выдаёт failure. Legacy/lifecycle compaction отмечена отдельно.
- `GroundedMCPSession`/`SourceReadController` — host-owned SDK, а не default
  server host. Для публичных SDK методов приведены test-only consumers;
  внешние production consumers не доказаны. Сохраняются issued-reference,
  range/project/snapshot binding, verbatim quote и two-action/token guards.
- Known OpenAPI fallback прослежен через `default_registry` →
  `CompositeRegistry.fetch` → `KnownOpenAPIRegistry.fetch` → builder.
  Он следует за local/hosted и требует explicit pack request.

References — именованные source edges, а не универсальный Python graph.
Рекурсивный/локальный helper edge сам по себе не доказывает default route;
это ограничение указано в rows. Точные line refs не являются dynamic coverage.

## Second pass: закрытие девяти OPEN по actual mechanism

Повторно прочитаны actual bodies и bounded named routes. Поиск точных
идентификаторов в `docmancer` и `tests` отделён от source-classification:
отсутствие caller не стало ни универсальной technical exemption, ни SPLIT,
ни REMOVE. Итог девяти owners — **7 technical candidates + 2 SPLIT**.

| Owner | Решение и доказанный механизм |
|---|---|
| `_answer_payload` | SPLIT: actual вызов `_agent_instruction(answer_type)` на строке 166 внедряет NL answer/navigation guidance; literal DTO отдельно. Есть direct test consumers `test_unified_docs_context_mcp_part02.py:140,169`, `test_unified_docs_context_mcp.py:394`; это не default MCP. |
| `_compact_payload` | Technical: копирование фиксированных полей/defaults и canonical support precedence через `_support_envelope`; нет question parsing, NL generation, scope inference или ranking. |
| `_fit_recovery_in_payload` | Technical: serialized-size threshold и fixed-key deletion order. Конкретный defect: может удалить confirmation/arguments fields при сохранённом action; candidate не разрешает использовать его как safety-preserving compactor. |
| `_packet_budget_inside_payload` | Technical: UTF-8 shell/marker accounting, explicit budget и min/max arithmetic; нет интерпретации темы. Four-byte approximation/128-token floor не доказывают fit tiny budgets. |
| `bounded_retrieval_issues` | Technical: exact status/support enum → диагностическое сообщение; английский output не является словарём question→tool. Actual patch handler вызывает другой `bounded_patch_retrieval_issues` на строке 484. |
| `_answer_project_context` | Technical: pure DTO projection и preservation confirmation fields, без `_agent_instruction`, question parsing или смысловой оценки evidence. |
| `_enforce_mcp_hard_cap` | Technical: JSON-size compaction/omission metadata по literal sections. Actual `_compact_mcp_payload:192` напрямую вызывает другой `compact_mcp_payload`. Legacy final return не rechecks cap и не обеспечивает canonical citation indivisibility; это defect, не неизвестная semantics. |
| `HostedRegistry.fetch` | Technical: configured registry/artifact transport, URL-encoded explicit identities, `download_url`/optional `sha256` и error protocol. Exact `base_url`/`DOCATLAS_REGISTRY_API_URL` config прочитан. Через `default_registry`/`CompositeRegistry` после local miss, затем `installer.py:45`; caller — explicit `install-pack`, не docs retrieval. |
| `compile_pack_from_url` | SPLIT: fetch/parse/hash/version grammar технические, но actual `registry.py:384` → `build_openapi_pack:226` → `compile_openapi:311` → `_derive_safety:598` добавляет semantic path-word safety exemption. Caller routes: explicit `--from-url` (`mcp_commands.py:120`) и interactive resolver-miss fallback (`:133`); TTY guard/пользовательский URL на `:191,199`. |

Default handler возвращает validated project/docs/patch projections
(`context_tools.py:480,634`), а бюджеты вычисляет на `:386,482`. Public handler
registration в `_docs_server_schema.py:18-25` не импортирует эти legacy helpers.
Project/admin/advanced handler branches (`project_tools.py:546,561,611-612`)
выбирают другие named compactors. Structured и text-fallback используют один
handler payload и общий terminal wrapper (`_docs_server_part01.py:242,252,311`);
text fallback не активирует legacy DTO/budget helpers. SDK direct imports не
объявлены невозможными, но universal graph для DTO mechanism не нужен.

Шесть definition-only owners, в отличие от `_answer_payload`, не имеют
найденных named test/source callers; positive consumers не приписаны.
Их source classification завершена по конкретным операциям выше, а не по
отсутствию calls. Existing guards/citation/confirmation требования не ослаблены.
Download-policy и legacy compaction defects оставлены явными limitations;
ни fixes, ни разрешение на reactivation не реализованы.

## Граница завершения

Полная source-mechanism классификация partition: **248/248, OPEN=0**.
Повторно проверены current source SHA256 и 1454 input nodes без пропусков;
consumer и boundary coordinates существуют. Audit decisions сами по себе
не требуют P1 approval. **Общее P0 closure/P1 acceptance не заявлено**:
30 SPLIT и 218 technical proposals должны быть согласованы с общим ledger
и product gate, но это не остаточная неизвестность данной классификации.
Никаких replacements, новых semantic lists, weakening tests, approval,
merge или P1 acceptance здесь нет.
