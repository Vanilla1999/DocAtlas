# P0: candidate ledger и реальные bridge/default boundaries

2026-10-06. **P0 ACTIVE / closure не доказан.**
Scope/gates исходного плана сохранены. Этот slice приоритизирует classification,
а не повторяет baseline. Production/gold/test contracts не менялись.

## Единая audit queue

[Runner](p0_candidate_ledger.py),
[compressed ledger](archives/p0-candidate-ledger.json.gz).
Runner проверяет все source hashes относительно первоначального 383-file
manifest; при изменении product file set или bytes прекращает выполнение.

| Candidate kind | Nodes |
|---|---:|
| String-containing collections | 5594 |
| Regex calls | 1276 |
| Membership branches | 1307 |
| String operations | 1697 |
| **Всего** | **9874** |

Каждый node имеет уникальный ID (path/full start-end span/kind), source/AST hashes,
точное source expression, enclosing symbol, assignment, classification status.
Call sites, imports, relative-import resolution и actual bridge exports сохранены.
Это candidate nodes, не 9874 доказанных словаря: nested containers и технические
DTO входят в scan намеренно; классификация не должна подменяться числом grep hits.
Validation обнаружила совпадения start span у chained operations (`lower().replace`);
ID исправлен на full start-end span, uniqueness проверяется самим runner.

**1440 candidates классифицированы**: 421 nodes из поимённо reviewed declarations/
mixed-function branches и 1019 structural export/case-normalization nodes. Технические retain candidates
по-прежнему не approved P1 exceptions. **8434 nodes ещё REVIEW-REQUIRED**;
часть из них уже имеет reviewed enclosing owner, но автоматического blanket
закрытия такого owner runner не делает. 157 frame decisions сохранены отдельно.

Дополнительные narrow technical candidates названы:
- `TECH-EXPORT`: literal `__all__` list/tuple/set задаёт Python interface. Реализации
  экспортируемых symbols проверяются отдельно; экспорт не доказывает dead code.
- `TECH-CASE`: atomic `.lower()`/`.casefold()` без arguments/custom mapping.
  Это generic case normalization, не тематический словарь; scope/identity/proof
  branches вокруг такого вызова остаются отдельными candidates. Нельзя переносить
  под эту отметку `_IRREGULAR_SINGULARS` или `.replace` semantic transformations.

## Реальные class bridges

[Probe](p0_bridge_closure_probe.py), [report](archives/p0-bridge-closure.json).
Прочитан `shard_compat.py`; проверены все девять найденных class-bridge installations:
SQLiteStore, WebFetcher, RetrievalDispatcher, PatchConstraintsService,
ProjectDocsService, ProjectContextService, UnifiedDocsContextService,
PatchReviewService, LibraryDocsApplicationService.

Для **348 actual wrappers** сохранены facade globals module, unwrapped implementation
module/qualname/line. Synchronization closure каждого facade вызвана напрямую
с временным object sentinel в существующем global, без business method calls;
проверено копирование в actual loaded shards и восстановление исходных objects.
Это отдельный audit process, не добавление alias/trigger в production.
**1273 candidate nodes** связаны с actual public class-method exports.

Следствие: facade globals достижимы в shards до business call; private monkeypatch
сам по себе не доказывает ablation. Решение technical bridge mechanism сохранить,
semantic declarations/consumers внутри shards мигрировать отдельно.
Этот probe закрывает конкретный facade→shard edge, не весь default/fallback call graph.

## Динамические parsers и fetcher factory

[Probe](p0_connector_boundary_probe.py), [report](archives/p0-connector-boundaries.json).
`agent._PARSERS` — exact extension→loader identity registry; `_import_class`
выполняет `importlib.import_module`, `getattr`. Все 8 suffix entries разрешились
в ожидаемые classes. Эти verified dynamic edges добавлены в ledger.
Техническое решение: retain registry/loading; suffix не интерпретирует NL question.

Static import closure с этими edges достигает **353 modules**, но не доказывает
runtime calls. Package `__init__` и direct SDK entry также могут быть доступны;
не считать неохваченный root SDK object автоматически unreachable.

Actual `factory.build_fetcher` для web/github/gitbook/mintlify/crawl4ai возвращает
`WebFetcher`. Поэтому direct `GitHubFetcher` exclusions нельзя приписывать
default factory lane. Class остаётся доступен direct SDK import и tests;
он включён в scope, а не удалён как dead code.

## D38: source-root/corpus rules

Прочитаны `pipeline/filtering.py` и GitHub selection/default exclusion paths.

| Symbol / consumer | Решение и граница |
|---|---|
| `_ROOT_HINT_SEGMENTS` → `infer_docset_root`/`_infer_scope_path` | REMOVE inferred root semantics; заменить explicit source root/verified manifest, не отменять same-host/path guards. |
| `_LOCALE_PREFIXES` → `_is_locale_segment` → `is_docs_url` | SPLIT: exact locale IDs отдельно от default suppression языков. RU seed допускается, canonical root отвергает RU mirror. |
| `_BLOCKLIST_PATTERNS` → `is_docs_url` | SPLIT thematic `/status`, `/changelog` exclusions vs file/transport constraints; не открывать network scope удалением filters. |
| `_STRIP_PARAMS` → `normalize_url` | SPLIT: hardcoded `from/source/ref` могут быть source-owned identity, не всегда tracking; URL normalization не должна уничтожать version/snapshot identity. |
| GitHub `_DEFAULT_EXCLUDE_FILES/FOLDERS` → `_is_excluded` → `_select_documentation_files` | SPLIT default corpus policy vs explicit external context config; empty exclusion lists возвращают defaults, не означают disable. |
| `_DOC_EXTENSIONS`/format detection | Technical retain candidate: actual file formats, не NL meaning. |

Pure helper probes фиксируют:
- `https://example.test/ru/docs/guide` отвергается с root seed и допускается с RU seed.
- `/docs/status` отвергается; другой host отвергается независимо от topic.
- GitHub selected folders `[docs,i18n]`: root `i18n/ru/guide.md` исключён defaults,
  но **nested `docs/i18n/ru/guide.md` допускается**. Не утверждать blanket RU ban.
- Explicit exclusion override допускает root RU/changelog/legacy candidates.
- `?from=source-owned-value&edition=1` нормализуется с потерей `from`.

Это наблюдения helpers, не network freshness или end-to-end recall proof.
Existing `test_filtering.py` + `test_fetcher_github.py`: **67 passed in 0.20s**,
[лог](archives/p0-connector-baseline-pytest.log). Required gates не заменены.

## Следующая работа

Разбирать оставшиеся 8434 scan nodes по owners, начиная с inline branches/regex
без concrete declaration decision. В ledger различать classification и caller
closure; привязать оставшиеся consumer edges к default/fallback entry points.
Не ставить P0 DONE по самому факту создания queue или по 353 importable modules.

## Дополнительный inline review после ledger validation

- D14: `_project_context_service_part01.dependency_mentioned_in_question:868–897`
  удаляет `flutter_` prefix и добавляет неназванную alias identity. Dependency cues
  и `_AMBIGUOUS_DEPENDENCY_NAMES` выбирают, разрешено ли вывести package из question.
  Callers: project context (`148`), service facade (`361–362`), project preflight
  (`_project_docs_service_part02:527`). **SPLIT**: explicit package metadata/literal
  bindings оставить; prefix alias и NL gating мигрировать. Это не D32 exact URL registry.
- D30: `_source_relevant_to_task:103–124` имеет независимый `scandoc`/`scan_doc`
  topic-specific rejection и filename/path exceptions; вызывается extraction loop
  (`13`). `_source_relevance_terms:127…` содержит отдельный stop list. **SPLIT**:
  subject relevance не переносить в новую таблицу; authority/source boundaries и
  bounded literal extraction сохранить. Alias builder removal это не выключает.
- D26: `technical_terms._COMMAND_PREFIX_RE/_COMMAND_SUFFIX_RE` — RU/EN semantic
  command cues, **REMOVE**; `_explicit_command_context` и `infer_technical_kind` —
  **SPLIT** NL labels vs shaped command/flag syntax. `extract_technical_terms:324`
  вызывает context helper; coerce/canonical/matching consumers вызывают kind inference.
  Название «technical» не делает free-form `run/command/команда` interpretation
  approved parsing exception. Source offsets/quotes/digit bounds сохранить.

Эти concrete branches добавлены в candidate decisions; regex-call handling
ledger расширено для reviewed declarations. Baseline повторно не запускался:
product bytes не изменились, новый evidence — source/caller classification.
