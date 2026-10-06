# Discovery literal dictionary exit — bounded slice

Primary: `/tmp/opencode/docatlas-stage3-integration-active`.
Baseline: `307c480cd7ffe2fff5a264167dcb09a7974ffc20`.
2026-10-07. **PARTIAL / full dictionary exit NOT DONE.**

Прочитаны `CONTINUE_HERE_RU.md`, `PARALLEL_REMAINING_EXIT_RU.md`,
`REMAINING_DICTIONARY_AUDIT_RU.md`, `CORPUS_POLICY_DICTIONARY_EXIT_RU.md`
в этом checkpoint directory. Network/commit/push не выполнялись.
Старые tests, gold, freeze, thresholds, config и curated JSON не менялись.
Локальный исторический gzip не тронут. Другие агенты параллельно меняют
compiler/proof files: их изменения не принадлежат этому исполнителю и не reviewed.

## 1. Только owned изменения

- `docmancer/connectors/fetchers/pipeline/discovery.py`
- `docmancer/docs/dart_official_docs.py`
- `docmancer/docs/discovery_candidates.py`
- Новый `tests/test_dictionary_exit_discovery_literals.py`
- Новый `tests/diagnostic_labels.dictionary_exit_discovery_literals.json`
- Этот новый checkpoint.

Не редактировались filtering/GitHub/config/curated registries и consumers.
Не добавлен новый public configuration contract.

## 2. Что удалено / сохранено

| Механизм | Решение и граница |
|---|---|
| discovery `_path_rank` | REMOVED: docs/documentation/reference/api/guide не повышают rank. Dedupe выбирает прежнюю strategy provenance, затем deterministic URL order. Membership до max_pages не расширяется. |
| discovery `_rank_urls_for_query`, `_rank_dartdoc_urls_for_query` | REMOVED: EN NL stopword lists. Остался прежний bounded literal lexical matching и stable tie order, без paraphrase/topic aliases. ASCII/token-length behavior не расширялся; RU lexical support этим не исправлен. |
| Dartdoc filename kind rank | PRESERVED / NARROWED: только exact `-class.html`, `-mixin.html`, `-enum.html`, `-function.html` suffix. Это идентичности generated Dartdoc entities, не знание о теме API/guide. Раньше concatenated path substring мог ошибочно засчитать kind внутри directory; новый suffix guard это исключает. |
| Dart guide seed sets | REMOVED: 15 topic seed occurrences (getting-started/providers/dispose/family/first-request/concepts/architecture/tutorial/navigation). 21→6 registered guide URLs. Оставшиеся шесть occurrences — прежние package-owned roots riverpod.dev/bloclibrary.dev. Никакие root/locale/framework replacements не угаданы. |
| go_router navigation seed | REMOVED: `https://docs.flutter.dev/ui/navigation` — inferred framework topic, не package API identity. Нет замены на docs.flutter.dev root. Прежние go_router API template и package page сохранены. |
| guide/API list priority | REMOVED: URL lists/candidates сортируются по literal URL, а не subject/guide superiority. Truncation может выбрать другой элемент, но только из прежнего конечного множества. Candidate why больше не объявляет guide preferred/API fallback. |
| package/ecosystem aliases | REMOVED: hyphen/space/punctuation→underscore candidate aliases; pub/flutter→dart collapse в двух owned helpers. Осталось trim/lower literal spelling. Невалидный literal Dart package identifier resolver отвергает ValueError до создания URL; invalid candidate lookup возвращает пустой список. Отличные protocol/ecosystem IDs не объявлены синонимами. |
| explicit identity→URL maps | PRESERVED: все 30 Dart mapping keys, все API version templates и package_page fields идентичны baseline; все 9 discovery keys и candidate URL sets идентичны baseline. Это отдельно проверено offline сравнением baseline/current module values. Каждый оставшийся guide URL — subset старого набора. |
| discovery protocol mechanics | PRESERVED: llms-full.txt/llms.txt, robots Sitemap directives, sitemap XML/index/gz locators, platform identities, Dartdoc index.json/HTML base resolution, strategy enum, response checks, fallback ceilings, original query gating, force_strategy, max_pages, seed provenance. Не заменены темой вопроса. |
| safety/transport/identity | Не ослаблялись HTTP/client security exceptions, effective Dartdoc host/path guards, explicit seed inputs, URL normalization, caller consent/network/byte budgets, version/provenance flags. Это не новый audit всех transport callers. |

`official_guides` DTO field name и strategy/confidence fields оставлены ради ABI:
они описывают registered identities, не полноту/точность snapshot или разрешение
network/edit. Technical source-strategy order сохранён, это не тематический boost.
Explicit identity map `firebase_firestore`→cloud_firestore API/package URL **OPEN**:
это не literal spelling alias и не признан technical exemption. Map сохранён по
запрету разрушать explicit identity→URL mappings; нужен отдельный owner identity
decision/caller allocation, чтобы удалить либо подтвердить эту связь.

## 3. Actual callers, не только imports

### URL discovery

- `docmancer/connectors/fetchers/_web/part01.py:201–211` вызывает
  `discover_urls` с exact base_url, client, platform, robots, max_pages,
  force_strategy, explicit seed_urls, fetched root_html и original query.
  Constructor того же файла хранит allowed_domains/path_prefixes policy;
  network/consent authority не производится ranking helper.
- `docmancer/connectors/fetchers/crawl4ai.py:109–115` вызывает `discover_urls`
  с base URL/platform/robots/max_pages без query/seeds. Далее `:145–149`
  повторно применяет robots/is_docs_url и page limit.
- Внутренние реальные edges: `discover_urls`→`_dedupe_and_rank`→literal query
  ranking; `_try_dartdoc_index_with_diagnostics`→Dartdoc literal ranking.
  Force-strategy и llms-full short-circuit не выданы за эти rank callers.

### Package/candidate identity и выбранный source

- `docmancer/docs/application/_library_docs_service_part01.py:121,167`
  canonical helper влияет на registry lane и Dart-specific branch. `:164`
  вызывает discovery_candidates_for, `:170` explicit API branch сохраняет
  package/version pub.dev URL и `docs_snapshot_exact`. `:234–247` вызывает
  has_official_docs/resolve/get_seed_urls: **nonowned** caller отдельно ищет
  первый non-pub.dev URL и признаёт hosts riverpod.dev/bloclibrary.dev.
  Поэтому sorted list не устраняет весь caller guide preference.
- Тот же файл `:308–328` вызывает nonowned curated_source_for/target_spec,
  если Dart branch больше не разрешён. Для pub/flutter riverpod текущий
  fallback содержит только старый riverpod.dev root, no seeds и один host:
  bounded new tests подтверждают strict subset, а не guessed replacement.
  Это не blanket approval других curated entries/callers.
- Тот же файл `:639–653` и
  `docmancer/docs/application/library_refresh_policy.py:126–137` вызывают
  canonical helper перед Dart diagnostics. pub/flutter теперь не автоматически
  получают Dart diagnostics. Внешние SDK consumers UNKNOWN.
- `docmancer/docs/application/_library_docs_service_part03.py:206–251`
  берёт candidate[0] для advisory arguments_patch и передаёт candidates в
  source options/next actions. Реальный downstream
  `docmancer/docs/domain/library_source_options.py:29–40,79–88` сохраняет
  `requires_confirmation=True`, `quality_guarantee=False`; confidence не
  сортирует кандидатов и не разрешает автоматическое fetch.
- `docmancer/docs/application/_library_docs_service_shared.py` импортирует
  helpers для этих shards. Это не самостоятельный execution edge.

**Parent needs / не редактировались:**

1. `docmancer/docs/curated_sources.py:56–62` всё ещё сводит flutter/dart/pub,
   javascript/typescript/node/npm; `:188–193` допускает только verified_seeds.
   Curated JSON, allowed_domains/path_prefixes/locked_versions/max_pages/source
   manifest validation и explicit URLs не менялись. Alias removal в owned
   helpers не означает all-caller identity cleanup.
2. `docmancer/docs/application/library_source_discovery.py:85–93` ещё выбирает
   pub metadata lane из dart/flutter/pub;
   `docmancer/docs/application/dependency_project_prefetch.py` и
   `docmancer/docs/pub_project.py` реально передают protocol ecosystem="pub".
   `docmancer/docs/ecosystem_adapters.py` тоже регистрирует adapter "pub".
   Это подтверждает, что pub — настоящий distinct protocol identifier,
   а не буквальное написание dart. Нельзя переименовать project/version identities
   или восстановить collapse только ради старых assertions.
3. Registry upsert сейчас echoes requested version в resolved_version даже для
   unversioned guide root. Actual new caller test обнаружил это; negative
   `docs_snapshot_exact=False` и `unversioned_official_guide` сохранены.
   Echoed version не certified exact snapshot. Registry consumer не allocated.
4. HTML `<base>` задаёт effective Dartdoc source; клиент должен ограничивать
   его original allowed host/path. Explicit seeds также merge без нового
   membership check. Existing transport policy, not lexical ranking, отвечает
   за permission. Полная caller-policy certification здесь не выполнена.

## 4. Corpus exclusions: BLOCKED, authorization отсутствует

Проверен текущий explicit selection contract, не создан новый:

- `docmancer/connectors/fetchers/pipeline/filtering.py:is_docs_url` имеет
  exact seed path/descendants и host ceiling; `_LOCALE_PREFIXES` и thematic
  `_BLOCKLIST_PATTERNS` до сих пор исключают mirrors/blog/changelog/etc.
  Signature не принимает approved finite corpus membership или explicit
  разрешение снять эти exclusions. URL root — не разрешение включить все topics.
- `docmancer/connectors/fetchers/github.py:388–445` выбирает по explicit
  Context7Config.folders либо file_patterns/default README/docs/doc paths,
  сохраняет doc suffixes и root docs exception. Empty exclude lists означают
  прежние defaults, не explicit authorization принять все файлы. Folder hints
  не удостоверяют разрешение legacy/legal/locale corpus.
- Existing allowed_domains/path_prefixes, version refs, max_pages и curated
  locked_versions/source manifests ограничивают transport/source identity,
  но не утверждают, какие previously excluded pages/files можно включить.
- Для удаления нужен owner-approved bounded corpus membership/selection и
  explicit decision по previously excluded categories/locales/files, привязанные
  к source/version и существующим budgets/consent. Такой контракт не найден.
  Не предложены новые public fields; не перенесены списки в config/prompts.

**Locale/topic/GH exclusions оставить OPEN/BLOCKED.** Их снятие без этого решения
расширяет crawl; ни blanket permissive, ни guessed English/root/framework scope
не являются dictionary exit. Ref/from/source URL normalization identity debt
из предыдущего checkpoint тоже не изменён.

## 5. Offline tests — normal conftest/hash shard, old reds сохранены

Команды: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider -q ...`.
Нет `--noconftest`, network и изменения old assertions. Новый module:
**61 behavioral instances / 20 base nodeids**, hash shard
`39e354a715bb772dcdcf4beab1329dfeb2de0c990eef2358dc61d186f25aab50`.

| Run | Результат |
|---|---|
| New discovery literal module | **61 PASS** |
| New + six technical modules | **106 PASS / 1 FAIL**, existing multipart warning |
| Old mixed bounded suites | **185 PASS / 26 FAIL** |
| In-memory baseline-owned substitution control, old mixed | **202 PASS / 9 FAIL** |
| Combined new + technical + old mixed | **291 PASS / 27 FAIL**, 1 warning |
| `git diff --check` | PASS |

Technical modules: `tests/docs/test_target_security.py`,
`tests/docs/test_content_trust.py`, `tests/docs/test_reference_hash_domains.py`,
`tests/docs/test_review_source_capabilities.py`,
`tests/docs/test_finalized_mcp_output_integrity.py`, `tests/docs/test_mcp_boundary.py`.
Единственный technical red — прежний
`test_patch_constraints_debug_compaction_preserves_contract_fields`, требует
advisory `answer_available=True`. Не исправлен и не waived green.

Mixed modules: `tests/test_dartdoc_pub_ingestion.py`,
`tests/test_dart_service_integration.py`, `tests/test_library_discovery_candidates.py`,
`tests/docs/test_dartdoc_discovery.py`, `tests/test_preindex_coverage.py`,
`tests/test_web_fetcher.py`, `tests/test_crawl4ai_fetcher.py`,
`tests/test_filtering.py`, `tests/test_fetcher_github.py`,
`tests/test_docs_fetch_transport.py`, `tests/test_docs_fetch_policy.py`.

Substitution control исполнял `git show 307c480c:<path>` только трёх owned
modules в их in-memory namespaces перед обычным pytest/conftest. Не checkout,
не полный baseline и не approval concurrent compiler/proof changes.
17 additional reds: 6 в dartdoc_pub_ingestion (hyphen alias, guide-first order,
третья inferred seed, flutter auto-resolution) и 11 в dart_service_integration
(pub/flutter collapse, auto seeds, refresh metadata/query и API lane compatibility).
Девять filtering inferred-root/sibling reds воспроизведены контрольным run.
Это bounded attribution, не blanket списание любых failures.

Логи вне Git: `/tmp/opencode/discovery-literals-old-mixed.txt`,
`/tmp/opencode/discovery-literals-baseline-owned-old-mixed.txt`,
`/tmp/opencode/discovery-literals-new-technical.txt`,
`/tmp/opencode/discovery-literals-combined.txt`. Не единственная точка provenance:
module lists/counts/control method/dispositions сохранены здесь.

Actual indexed MCP/stdio/self-host/full CI/rebuilt wheel/frozen quality floors
не запускались в этом allocation. Stdio fixture script делает disposable commits,
поэтому не запущен при запрете commit. Ранее red self-host quality остаётся red;
scoped technical checks его не заменяют. Parent выполняет общий integration gate.

## 6. Source pins этого bounded slice

| Path | SHA-256 |
|---|---|
| `docmancer/connectors/fetchers/pipeline/discovery.py` | `be088eb6eafce54499b3f9ada8e9aaa722807c626f15f5c3e4094927e5c981d7` |
| `docmancer/docs/dart_official_docs.py` | `a07b523c593353de33ba9c60da8c33a8f025f16223d6f697f3afef6c2840b1b7` |
| `docmancer/docs/discovery_candidates.py` | `019a1aa39492011675143c5eba734df2984a3ce9bacf18339616a832171e7817` |
| `tests/test_dictionary_exit_discovery_literals.py` | `bab0f0700b8d49ea30e918bf19b7a1b8890ccec44baefb967cf82db7a8fb975e` |
| `tests/diagnostic_labels.dictionary_exit_discovery_literals.json` | `0aa760ed480e48c59343298e06967b475aaaf86b4445157bd516249424da91b0` |

**Full NOT DONE:** exclusions/explicit corpus authorization, cross-module alias/
preferred-source consumers, questionable explicit package alias, all transport
callers, broader curated seed/identity audit, sibling compiler/proof exit,
quality restoration и release validation остаются вне scoped completion.
