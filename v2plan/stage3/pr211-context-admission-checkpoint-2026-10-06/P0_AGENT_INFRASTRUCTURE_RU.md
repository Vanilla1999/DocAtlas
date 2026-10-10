# P0 infrastructure — второй проход всего partition, не закрытие P0

2026-10-06. Классифицированы **все 592 units / 102 файла** из
`archives/p0-agent-input-infrastructure.json.gz`. Каждый входной `(path, owner,
source_sha256)` имеет отдельную строку в
`archives/p0-agent-infrastructure-decisions.json`. Production, tests, gold и общие
аудитные файлы не изменялись. Применимых `AGENTS.md` в рабочем дереве и его
предках не обнаружено.

| Решение | Units |
|---|---:|
| TECHNICAL-RETAIN-CANDIDATE | 429 |
| SPLIT | 155 |
| REMOVE | 8 |
| OPEN | 0 |

**Это полное покрытие входного partition, но не доказательство полного closure.**
Во втором проходе рассмотрен **весь исходный OPEN set: 261/261**. Переходы:
**178 → TECHNICAL-RETAIN-CANDIDATE, 83 → SPLIT**. Каждая такая строка имеет
`previous_decision=OPEN`, `review_basis=second-pass-explicit-owner-contract` и
конкретную source contract reference. Нет default-rule «остальное technical».

Ноль OPEN означает завершённую классификацию candidate mechanisms, **не closure
внешних/runtime consumers** и не разрешение на production migration.
Technical-retain — предложенное исключение для candidate expressions,
не blanket approval файла или всех операций owner. REMOVE описывает механизм
для последующей миграции, не выполненное изменение production.

## Метод и проверка pins

- Прочитаны и AST-разобраны реальные production sources; все 592 owners найдены,
  включая nested functions, assignments и module expressions. Полные owner bodies
  использовались для извлечения actual calls и boundary conditions. Для явных решений
  отдельно рассмотрены механизмы, callers, imports и связанные audit observations.
- В каждой строке есть source range, все входные candidate node IDs, candidate
  expressions и actual direct call dependencies. OPEN сохраняет конкретный
  source mechanism, который ещё нельзя безопасно отнести к retained/removed.
- Consumer refs — конкретные named relevant paths с файлом, строкой и owner.
  Первый проход установил same-module/explicit import и условные wildcard/shard
  refs; второй перечитал эти именованные paths и локальные consumers каждого
  рассматриваемого owner. `named_consumer_scope` перечисляет фактический scope.
  Это **не universal runtime Python graph**. Wildcard/generated facade bindings
  остаются условными. До восьми refs первого и десяти refs второго прохода;
  bounded список не означает exhaustive closure.
- **102/102 source SHA256 совпадают** с входными pins; missing/extra/duplicate units
  не допускаются. Input gzip SHA256:
  `2f001bd66208c7b7239b91fb11b151795f57c0b3d1ba03ea85ba58586c7f6547`.
- Дополнительно сверены имеющиеся manifest pins для `DICTIONARY_INVENTORY_RU.md`,
  `archives/p0-bridge-closure.json`, `archives/p0-connector-boundaries.json`:
  совпадения 3/3, результаты включены в JSON. Neighbor/symbol/config audits
  используются как ограниченные supporting observations, не новый end-to-end proof.

## Ключевые разделения

### D11 / D12 / D20: lexical ranking — не technical exemption

`core/_sqlite_store_part03.py:_ranking_candidate` — SPLIT: topical boilerplate,
task/action/project signals и authority penalties отдельно от raw BM25, stable IDs,
source-local complete phrase с отрицанием и trace. `query`, `_search_rows`,
`_lexical_match_trace` также mixed: stopword/generic filtering нельзя объявлять SQL
syntax. `_strip_stopwords` — REMOVE semantic filtering, включая RU
`ответь/укажи → evidence/id/ids` suppression.

`retrieval/_dispatch_shared.py:_intent_source_score`, `_snippet_intent_score` —
REMOVE: tutorial/reference/advanced и FastAPI-specific API/path boosts. Consumer
`_dispatch_part02.py:_rerank_intent_matches:255–299` — SPLIT; сохранить project-body
bypass, exact/source provenance и rank trace, не весь heuristic scorer.

Default lexical dispatcher вызывает `store.query → filter → exact supplement →
intent rerank → source cap` в `_dispatch_part01.py:155–172`. Те же post-processing
helpers вызываются при allow-degraded fallback (`174–190`) и в других lanes.
Проектная ветка rerank имеет отдельный bypass, поэтому library-specific scores
не приписываются каждому project-only запросу.

`query_planning._concept_queries` — REMOVE ручного EN stopword proposal mechanism;
`build_query_plan` — SPLIT с сохранением original/requirements/filter hashes и caps.
Дополнительные NL stopwords в discovery/Dartdoc seed ranking — SPLIT, не parsing-only.

### D31: source syntax vs navigation heuristics

Exact import/path/declaration, Markdown fences/headings и lockfile syntax —
technical candidates. Это не утверждение полноты regex parsers для всех языков.
`code_context` query/reference expansion сохраняет OPEN/SPLIT там, где involved
`_LOW_SIGNAL_TERMS`, `_GENERIC_SOURCE_TERMS`, `tsd/browser` injection или noise demotion.
Caps, containment, unknown symbols и navigation-only limitations сохраняются.

Patch-context bottom/sheet/dialog → inline-menu replacement goal/operation/step —
REMOVE. Named MenuPageBuilder/openMenu/QR/capability templates вместе с source/API
refs — SPLIT. Synthetic camel/snake variants не дают exact symbol ownership proof.
`_looks_like_code_line` содержит `Future`, `Provider`, `ref.`: структурная пунктуация
и library-shaped snippet heuristics разделены, а не объявлены техническими целиком.

### D32: explicit identity → locator, не authority/freshness proof

Curated ecosystem/package/version identities, explicit adapter/resolver registry,
validated templates и verified seed gating — proposed technical candidates.
Сохраняются exact normalized lookup, version locks, URL/fetch boundaries. Никаких
новых registries/dictionaries не добавлено.

`documentation_evidence.assess_documentation_evidence` — SPLIT: actual code
подтверждает exact version по substring requested_version в URL (`91–93`). Locator
spelling не доказывает snapshot. Authority/source/registry-host enums отдельно
technical candidates, с ограничением на provenance producers и official labels.

### D38: corpus eligibility vs URL security

`pipeline/filtering.is_docs_url` — SPLIT: HTTP(S)/same-origin boundaries отдельно
от root widening, locale exclusions и topic/format blocklist. `_is_locale_segment`
— REMOVE manual corpus classification; caller-explicit locale/source binding не
должен теряться. `infer_docset_root` и `normalize_url` — SPLIT: docs-host/root hints
и stripping ref/from/source способны менять scope/identity.

`DocsFetchPolicy` и policy-aware transport — technical security candidates:
userinfo/private-network rejection, host/path boundaries, redirect revalidation,
DNS pinning и bounded responses нельзя ослаблять вместе с corpus rules.
Source continuation отдельно сохраняет catalog/project/content hashes, active
generation metadata, no-follow component opening и bounded regular-file reads.

Исторический `GitHubFetcher` имеет **SDK**, не default factory reachability:
`factory.build_fetcher:45–75` всегда создаёт WebFetcher. Default SDK patterns,
exclusions/rank/README fallback — mixed; explicit glob/ref/config grammar отдельно.
Existing connector probe подтверждает observable selection, но сам прямо исключает
HTTP/freshness/end-to-end ingestion claims.

## Reachability и незакрытые доказательства

| Reachability | Units |
|---|---:|
| default | 21 |
| SDK | 17 |
| static-edge-only | 470 |
| unresolved | 84 |

`default` — source-visible flow выбранного entrypoint, не выполненный public MCP
replay. Source conditions/branch bypass остаются обязательными. Отдельная категория
fallback не назначалась без достаточного доказательства конкретной fallback-only
границы: наблюдаемые degraded edges указаны выше, общие helpers не названы
fallback-only. Внешние SDK callers, generated wrappers, wildcard facade overrides и
configuration-dependent lanes не закрыты обычным AST scan. Отсутствие consumer ref
не является доказательством dead code.

### Результаты второго прохода по оставшимся owners

- **Web/discovery/extraction:** literal sitemap/robots/XML/JSON/HTTP fields,
  redacted ledger DTO и exact commit/blob/size acquisition — technical candidates.
  First-main/noise/version-note/source-link stripping, directory/entity eligibility,
  HTML signature guesses, fallback widening и dedup corpus projection — SPLIT с
  отдельными transport/scope/byte/cancellation guards. SDK Crawl4AI не превращён
  в default factory path. Admonition/code CSS formatting — source syntax, не NL
  inference; HTML metadata остаётся untrusted.
- **Core/structured chunking:** exact generation metadata-only SQL, parent/atom
  expansion, UTF-8/span/hash/fence grammar и typed config DTO — technical candidates.
  Retention DTO не распространяется на nested routers. Legacy heading parser
  не объявлен полноценным Markdown parser.
- **Impact/Git:** bounded NUL-safe read-only Git protocol, exact diff declarations,
  continuation/schema/escaping и fail-closed truncated authoring DTO — technical.
  `docs/INDEX.md`/role → authority, directory → module, fallback filename → docs,
  test-name → role и ordered evidence dropping — SPLIT. Actual catalog/Git source
  identity, dirty/indeterminate checks и очистка allowed_edits сохраняются.
- **Patch/code navigation:** literal source refs/escaped identifier grammar/DTO caps
  — technical. Pattern/why → current behavior, refs-present → high confidence,
  substring alternatives without refs, compact matching, skip policy и graph task
  boosts — SPLIT. Explicit changed files не дают blanket edit approval; not_found
  ограничен реально просмотренным corpus; navigation-only остаётся no-answer.
- **Manifest/registry/project:** v2/flat DTO и explicit identity/config grammar —
  technical. `docs_snapshot_is_exact` substring в URL, manifest exact qualification,
  README/architecture/ADR/file-role discovery, catalog lifecycle → track policy и
  Dartdoc default budget widening — SPLIT. Explicit catalog/host/path/version
  boundaries сохраняются. Host-policy строки `agent_contract` не выданы за DTO-only.
- **Retrieval/contextual indexing:** `_apply_router` явно классифицирован SPLIT:
  configured regex → question filters — semantic policy даже без hardcoded списка
  в модуле. Dispatcher composition — SPLIT, exact readiness/parity/trace DTO —
  technical. `_PLAIN_WORD` подавляет lowercase call-shaped aliases; metadata
  defaults могут изготовить active/current/synchronized eligibility. Эти механизмы
  разделены с exact symbol syntax и project/source filters, не названы unknown.
- **Embedding/runtime/eval:** actual dimension probes/cache bytes/vector payload/
  ownership/upsert parity и explicit backend asset/env/protocol — technical.
  Pinned version не доказывает download integrity; occupied port не доказывает
  service health. Frozen scenario/threshold/story fixtures и measurement/report
  schemas — isolated eval contracts, не production NL dictionaries. Locale-marker
  contamination labels — SPLIT; diagnostic policy не разрешает live exclusion.

84 unresolved **reachability** не смешиваются с завершённой классификацией owner
mechanisms. Для них нет доказанного named caller/default execution; внешние SDK,
generated wrappers и installed-config behavior требуют отдельных проверок.
Никакие eval scenarios не мигрировались в gold; новые словари, replacements и тесты
не добавлялись. Output shape сам по себе не служил основанием retention: отдельно
проверены payload/schema meaning и semantic consumers.

Проверки этого агента: JSON/schema enums, exact input/output key coverage, candidate
node coverage, source hashes, owner location и cited artifact pins. **Тесты и HTTP
не запускались**; прежние subset results не выдаются за новые проверки. P0 остаётся
ACTIVE; полный partition ledger готов для reconciliation. Классификационных OPEN
нет, но runtime closure, P1 technical exception approval и regression/migration
проверки не закрыты.
