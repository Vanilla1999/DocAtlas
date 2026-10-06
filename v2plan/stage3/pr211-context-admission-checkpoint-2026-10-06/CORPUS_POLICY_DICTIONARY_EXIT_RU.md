# Bounded corpus / delivered-policy dictionary exit

Baseline: `adc9abf8`; primary `/tmp/opencode/docatlas-stage3-integration-active`.
2026-10-06. **PARTIAL / full dictionary exit NOT DONE.** Commit/push/network не выполнялись.
Работа соседних SDK/audit исполнителей не изменялась. Старые tests/gold/freeze/thresholds
не правились; существующий локальный gzip не трогался.

## Изменённые файлы этого исполнителя

- `docmancer/connectors/fetchers/pipeline/filtering.py`
- `docmancer/connectors/fetchers/github.py`
- `docmancer/mcp/agent_workflow_contract.py`
- `docmancer/templates/agent_contract.md`
- `docmancer/templates/skill.md`
- `docmancer/templates/claude_code_skill.md`
- `docmancer/templates/claude_desktop_skill.md`
- `tests/test_dictionary_exit_corpus_policy.py`
- `tests/diagnostic_labels.dictionary_exit_corpus_policy.json`
- Этот новый checkpoint report.

Остальные templates не переформатированы и не изменены. Discovery registries,
MCP descriptions/resources и корневой `SKILL.md` не входят в allocation.

## Решения по механизмам

| Механизм / entry point | Решение | Реальная граница |
|---|---|---|
| filtering `_ROOT_HINT_SEGMENTS`, `_infer_scope_path` → discovery/web/crawl4ai | REMOVED | Нет guessed parent/sibling scope; сохраняется точный seed path и его descendants с segment boundary. `/docs-x` не проходит для `/docs`. |
| filtering `infer_docset_root` → `_web/shared.py`, `_web/part01.py`, crawl4ai | REMOVED | Legacy hook возвращает `None`; existing callers сохраняют точный URL. Ни docs/api host labels, ни llms filename не удостоверяют docset identity. Явные metadata не меняются. |
| GitHub `_rank_file` → `_select_documentation_files` | REMOVED | Убраны docs/doc/documentation/README/root thematic priorities. Только explicit folder order, затем deterministic lexical path order. Membership corpus не расширен. |
| Workflow `scope_planning`, `free_form_lookup`, `gap_resolution`, examples | REMOVED | Нет topic→scope, RU→EN guessed source/action examples, compulsory semantic decomposition или inferred subquestions. Original question + explicit lookups (≤5) + cited context. |
| Templates canonical contract и три final-evidence paragraphs | REMOVED | Нет inferred logical implication/proof/completeness, scope из темы, automatic diagnostic rephrase, hard-stop absence→edit. Separate explicit mutation target/authorization обязательны. |
| filtering `_LOCALE_PREFIXES`, `_is_locale_segment` | BLOCKED / OPEN | Удаление допускает ранее запрещённые mirrors; API не имеет explicit locale authorization. Список остаётся, не объявлен technical exception. |
| filtering thematic `_BLOCKLIST_PATTERNS` entries | BLOCKED / OPEN | blog/changelog/release/status/pricing/settings/print exclusions ограничивают текущий corpus; удаление расширяет membership. Нужен отдельный explicit corpus contract, не blanket permissive. |
| GitHub `_DEFAULT_EXCLUDE_FILES/FOLDERS`, `_is_default_doc_path`, constructor defaults | BLOCKED / OPEN | Удаление исключений расширяет corpus (legacy/archive/legal/locale), удаление implicit roots без contract либо расширяет, либо обнуляет SDK selection. Не переносились в prompt/config. |
| filtering `_STRIP_PARAMS` | SPLIT / OPEN | utm/fbclid/gclid — transport tracking; ref/from/source могут быть meaningful URL identity. Нормализация не изменена: требуется отдельный caller/identity audit. |

Removal root inference сознательно уменьшает sibling discovery и может разделить
legacy URL groups. Explicit docset/source mappings, version refs, hashes/provenance,
network/consent/budget authority не подменяются inferred host-root identity.

## Сохранённые технические таблицы и guards

| Механизм | Основание / проверка |
|---|---|
| GitHub `_DOC_EXTENSIONS`, protocol tree/blob parser, headers, explicit folder/file exclusion syntax | Форматы и explicit transport/scope; тестируются suffix selection и exact exclusions. Не query→answer table. |
| `Context7Config` fields и explicit branch/version refs | Source configuration/protocol. Metadata repo/branch/file_path/docset_root/fetched_at проверены новым offline single-file test. |
| filtering HTTP(S), netloc, binary suffix/auth-account patterns | Concrete transport/file-type/security barriers; не удалены. Userinfo и отсутствующий HTTP seed отвергаются. |
| Exact path segment boundary и `_safe_scope_path` | Fail-closed против raw/encoded/multiply-encoded dot segments и backslashes. Никаких guessed parent roots/locales. |
| `ContentDeduplicator`, normalization | Существующие SHA-256/dedup semantics сохранены и проверены. Не source span proof и не authorization. |
| `PUBLIC_TOOL_ORDER`, `CONTRACT_SCHEMA`, canonical JSON/hash tool records | Runtime protocol/schema identity. Новый test recomputes contract/schema hashes и проверяет isolated deep copies. |
| version_binding/recovery/prepare/status technical policy | Exact/historical/current lockfile binding, terminal-success retry, explicit/returned lifecycle actions, status not discovery, hard stop сохранены. |
| robots, size, redirect/network/consent/budgets | Outside owned files; не редактировались. Existing fetch transport/policy/web/crawl4ai tests входят в run. |

## Проверки (normal conftest, offline, без изменения старых assertions)

Environment: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`, `.venv/bin/python -m pytest -p no:cacheprovider`.

| Run | Результат |
|---|---|
| Новый corpus-policy module | 36 PASS: 35 behavioral instances, 1 schema; 11 base nodeids. Hash shard `d68011233a9555b3057ad4f67584670a1d6ae6d4815e34862e77532be0390b8e`. |
| Новый module + 6 security suites | **82 PASS**, 1 existing multipart deprecation warning. |
| Полный bounded combined run ниже | **239 PASS / 46 FAIL**, 1 warning; не объявляется green. |
| In-memory slice-only `adc9abf8` substitution control, только old mixed suites | **176 PASS / 27 FAIL**. Не full-baseline checkout: заменены только owned Python modules и template renderer, остальные файлы current shared tree. |

Security suites: `tests/docs/test_target_security.py`, `test_content_trust.py`,
`test_reference_hash_domains.py`, `test_review_source_capabilities.py`,
`test_finalized_mcp_output_integrity.py`, `test_mcp_boundary.py`.

Mixed suites: `tests/test_filtering.py`, `test_fetcher_github.py`,
`test_docs_fetch_transport.py`, `test_docs_fetch_policy.py`, `test_web_fetcher.py`,
`test_crawl4ai_fetcher.py`, `tests/docs/test_self_host_agent_contract_surface.py`,
`test_host_scope_contract.py`, `test_agent_question_planning_contract.py`,
`test_action_packet.py`.

Новые 19 failures относительно slice-only control: 9 old inferred-root/sibling
assertions, 7 topic-scope host assertions (1 policy + 6 rendered guides), 3 removed
lookup-example/decomposition/gap-policy assertions. Остальные 27 reproduced reds:
self-host packet missing sources, module context availability, прежние template
expectations и mutation/proof/patch compatibility. Control не доказывает root cause
для всей baseline или concurrent SDK slice. Existing assertions не ослаблялись.

MCP stdio smoke/self-host quality rebuild/full CI не выполнялись. В частности smoke
создаёт fixture commits, а этот allocation запрещает commits. Старые quality reds
не закрываются green technical tests. `git diff --check` PASS.

## Discovery registry audit: inspect-only, не allocation

- `docs/discovery_candidates.py:_KNOWN_DISCOVERY_CANDIDATES`: exact library/ecosystem→URL
  candidates, не тематический query alias. Preserve explicit mapping; confidence/preference
  не удостоверяет snapshot/proof. `_canonical_ecosystem` aliases требуют symbol audit.
- `docs/dart_official_docs.py:DART_PACKAGE_OFFICIAL_DOCS`: explicit package→URL/template
  maps сохранять. Curated thematic guide seed sets и guide/API priority остаются OPEN;
  это не автоматически допустимая semantic discovery exemption.
- `docs/curated_sources.py` + JSON: explicit identity/version→URL, allowed_domains,
  path_prefixes, locked_versions, max_pages, validation/provenance сохранить.
  Ecosystem alias normalization и preferred seed selection — отдельный audit.
- `connectors/fetchers/pipeline/discovery.py:_path_rank`: live thematic
  docs/documentation/reference/api/guide path boost (около line 544) остаётся OPEN.
  `_rank_urls_for_query` также содержит NL stopwords. llms/robots/sitemap paths
  содержат protocol locators; не удалять скопом. Module не owned.

## Parent integration dependencies / remaining OPEN

1. Для удаления locale/topic/generated exclusions нужен explicit bounded corpus
   selection contract в discovery/callers. До allocation/решения — нынешние exclusions
   остаются BLOCKED, не permissive и не moved dictionary.
2. Delivered policy всё ещё конфликтует с non-owned `_docs_server_shared.py`,
   `_docs_server_tool_data.py`, `_docs_server_resources.py` и корневым `SKILL.md`:
   там остались topic scope / semantic decomposition / gap splitting instructions.
   `public_agent_contract()` продолжает **честно hash-ить actual runtime descriptions**;
   его новая identity не доказывает cleanup этих descriptions.
3. Parent должен согласовать эти surfaces и release/host consumers нового identity;
   не восстанавливать removed semantic fields ради old compatibility tests.
4. Full D32/D33/D38 и all-runtime dictionary exit остаются OPEN. Это scoped partial
   implementation, не acceptance полного corpus/delivered-policy exit.
