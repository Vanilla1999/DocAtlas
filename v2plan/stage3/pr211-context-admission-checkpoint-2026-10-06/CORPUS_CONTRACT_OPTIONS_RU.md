# Corpus contract: current membership и варианты owner decision

2026-10-07. **READ-ONLY production audit; FULL EXIT NOT DONE.**
Baseline/HEAD/origin PR branch: `9488cb66ab989f6f65bafbfae7d1eb3f844ce0a3`.
Изолированный worktree: `/tmp/opencode/docatlas-next-corpus-audit-9488cb66`.
Primary `/tmp/opencode/docatlas-stage3-integration-active` не редактировался.
Единственный созданный файл — этот checkpoint. Нет production/config/test/gold/
threshold/manifest edits, network/crawl, commit/push или secondary agents.
Предсуществующие local `CONTINUE_HERE_RU.md`, untracked handoff и `.venv` symlink
не изменены. Прочитаны четыре заданных checkpoint и current production consumers.

## 1. Приоритетный результат, не implement decision

1. **P0 — сначала определить контракт на границе callers.** `allowed_domains` и
   `path_prefixes` — transport ceiling, не точная membership. В non-manifest
   `DocsPrefetchService` они проверяются при target resolution, но НЕ передаются
   в `agent.add`; refresh передаёт. Нельзя объявить bounded contract готовым по DTO.
2. **P1 — минимальный вариант для рассмотрения: конечные exact URLs / immutable
   file rows, только в уже разрешённой границе, без discovery expansion.** Для
   произвольного web такого единого execution mode сейчас нет. Нужна отдельная
   authorization на caller/consumer slice; новые public fields здесь не предлагаются.
3. **P2 — explicit subtree contract только после конкретной owner authorization
   на весь subtree, включая ранее скрытые locale/topic pages.** Просто удаление
   `_LOCALE_PREFIXES`, blocklist или GitHub defaults расширяет membership.
4. **P3 — отложить изменение membership:** оставить BLOCKED exclusions как
   открытый semantic debt. Это допустимый stop, но не dictionary exit.

Варианты ниже не выбраны и не реализованы. Нельзя перенести locale/topic/legacy
словари в YAML/JSON/prompt и назвать это explicit contract.

## 2. Что именно означает current membership

Здесь membership — правило допуска candidate page/file и последующий bounded
selection, НЕ перечень реально indexed documents. Сетевой snapshot/index в этом
audit не открывался. Точный page set зависит от source response, strategy,
dedup/rank, extraction, content duplication и ceilings. Без конкретного capture
невозможно честно перечислить все фактически indexed URLs.

### 2.1 Shared web predicate — `pipeline/filtering.py:142–205`

Candidate разрешён тогда и только тогда, когда одновременно:

- candidate и base имеют `http`/`https`; candidate netloc непустой; нет username
  у candidate/base; netloc сравнивается case-insensitive, включая port. Scheme
  не обязан совпадать, subdomains этим predicate не разрешаются;
- paths проходят `_safe_scope_path`: bounded repeated percent decoding,
  запрет backslash и `.`/`..` segments;
- case-sensitive candidate path после удаления trailing slash равен точному
  base path либо его segment-boundary descendant. Для root path охват — весь host;
  sibling/parent inference нет; `infer_docset_root` всегда `None`;
- locale rule не сработал: если НИ ОДИН segment seed не recognized locale, первый
  relative segment candidate не должен входить в
  `ar,bn,de,es,fr,id,it,ja,ko,nl,pl,pt,pt-br,ru,tr,uk,vi,zh-hans,zh-hant`.
  Recognition lowercases и заменяет `_` на `-`. Это не общий language detector:
  `/docs/ru/x` запрещён от `/docs`, `/docs/api/ru/x` разрешён; `en`, `hi`, `sv`
  не в списке. Наличие recognized segment В ЛЮБОМ месте seed отключает veto;
- path+query не совпал с regex blocklist (case-sensitive):
  `/blog`, `/changelog`, `/release-notes`, `/status`, `/pricing`, `/login`,
  `/signup`, `/register`, `/sign-in`, `/sign-up`, `/account`, `/settings`
  с `(/|$)`; `/search(\?|$)`; `[?&]print`, `/_print(/|$)`, `/print\.html`;
  terminal suffix `pdf|zip|tar|gz|png|jpg|jpeg|gif|svg|mp4|mp3|woff|woff2|ttf|eot|ico`.
  Binary regex terminal относительно path+query: suffix с query не обязательно
  совпадает. Это строковые правила, не content-type verification.

`normalize_url:47–80` удаляет fragment, canonicalizes, убирает trailing slash,
strips `utm_source,utm_medium,utm_campaign,utm_term,utm_content,ref,from,source,
fbclid,gclid`. Последние три generic слова могут быть meaningful identity/version;
нынешняя нормализация не доказывает equivalent source. Например
`/docs?a=1&source=v1&ref=v2&utm_source=x` превращается в `/docs?a=1`.

### 2.2 Discovery → WebFetcher — не один predicate

`agent.add → ingest_url:796 → _get_fetcher:739 → factory.build_fetcher:16`
**всегда создаёт WebFetcher**, даже с provider `github`/`crawl4ai`/`gitbook`/
`mintlify`. CLI gitbook также использует factory. `fetcher=` в SDK может заменить
его; внешние injection consumers UNKNOWN. Наличие class/import не default execution.

`WebFetcher.fetch` (`_web/part01.py:120–272`):

- Сначала transport policy validation; затем manifest / GitHub blob / direct text /
  direct Dartdoc early-return branches. Они не вызывают shared topic/locale predicate.
- Иначе landing fetch, platform detection, conditional robots и `discover_urls`.
  Shared discovery (`discovery.py:87–271`) first returns llms-full при пустом query,
  затем Dartdoc index; forced strategy возвращается отдельно и не merge-ит seeds.
  Успешные early returns также не merge-ят explicit seeds.
- Обычный merged path: llms index, robots/platform/regular sitemap, nav crawl,
  bounded nav fallback, затем explicit seeds. Sitemaps/nav используют `is_docs_url`;
  llms index parsing НЕ фильтрует membership; Dartdoc uses отдельный same-scheme/
  same-netloc/path predicate (`:390–398`), иногда от HTML `<base>`.
- `_dedupe_and_rank:506–540`: normalized URL, strategy order llms → robots sitemap →
  sitemap → platform sitemap → nav → fallback → seeds, затем lexical URL.
  Query adds literal Latin path match rank; thematic path boost/stopwords уже нет.
  Cap `[:max_pages]` применяется ДО per-page rejection, поэтому rejected llms links
  могут занять candidate slots. Seeds не гарантированы ни при cap, ни при collision:
  duplicate llms/seed URL сохраняет `LLMS_TXT`, то есть теряет seed bypass.
- `_web/part02.py:19–38`: robots guard; `SEED_URLS` bypasses **весь** `is_docs_url`,
  а не только locale/topic. Остальные pages повторно фильтруются. Per-request
  `DocsHttpClient` policy остаётся обязательной; seed не даёт network consent.
- llms-full early return принимает один aggregate body: page-level locale/topic
  membership внутри тела не проверяется. Максимум один URL не равен одной page
  содержания. Separate protocol/content/byte ceilings не semantic membership.
- Canonical source label (`part02:150–151`) у seed принимается без `is_docs_url`;
  это metadata/source attribution, НЕ доказательство разрешения fetch этого host.
  Requested/fetch/canonical identities требуют отдельного binding review.

`DocsFetchPolicy` (`docs/fetch_policy.py:46–170`) проверяет HTTP(S), credentials,
host/DNS/private IP, path, redirects через transport. Default `allow_subdomains=True`:
allowed host включает его subdomains; empty paths не ограничивают path.
`_policy_for` выводит hosts из supplied URL+seeds при отсутствии allowlist, не paths.
`_fetch_page` создаёт client с `self._fetch_policy`, а не локальным результатом
`_policy_for`; equivalence этих boundaries при empty supplied policy не доказана.
Это дополнительная caller/transport dependency, не найденный terminal exploit.

### 2.3 Crawl4AI — callable separate lane

`Crawl4AIFetcher.fetch:84–151 → discover_urls → robots → is_docs_url → cap →
_extract_pages`. Нет `seed_urls`, `allowed_domains`, `path_prefixes`, source manifest
или explicit version contract в constructor. llms-full возвращается до page filter;
обычные candidates всегда проходят predicate, seed bypass нет. Class uses raw
`httpx` with redirects и separate browser extraction, не WebFetcher secure client.
Default factory его НЕ создаёт. Direct SDK/injected fetcher — callable; внешняя
runtime частота UNKNOWN. Нельзя распространить WebFetcher policy guarantees на него.

### 2.4 GitHubFetcher — точные правила legacy/direct SDK

`github.py:95–200` callable, но production instantiation в repo не найден;
default provider GitHub идёт через WebFetcher. Direct external SDK usage UNKNOWN.

- Repo URL без path: default branch API (при failure `main`); recursive tree,
  optional `context7.json`; config `branch` может заменить даже supplied ref.
  `previousVersions` и `branchVersions` добавляют refs с тем же selection, без
  requested-version intersection. Нет max_pages/immutable commit verification
  в этом class; tree API `truncated` не проверяется.
- Parser (`:253–277`) не различает tree/blob: **ЛЮБОЙ trailing path** становится
  `explicit_file`, и fetch сразу `_fetch_single_file`. `/tree/v1/docs` — попытка
  raw file `docs`, НЕ directory traversal. Slash-in-ref parser не поддерживает.
- Single-file mode bypasses extensions/default roots/exclusions/context7/extra
  versions. Это explicit file mode с raw client, не уже готовый secure corpus contract.
- Repository selection (`:388–445`): при nonempty config `folders` включаются
  descendants folder **плюс все root files** с `.md,.mdx,.txt,.rst,.ipynb`.
  При default constructor patterns: только `README.md` и `docs/`/`doc/` descendants
  с этими suffixes (больше чем текст default `**/*.md` предполагает).
  Custom `file_patterns` используют `_matches_patterns`, без общего suffix guard;
  пустой list constructor снова включает defaults.
- Затем filename exclusions: exact case-sensitive basename
  `CHANGELOG.md,changelog.md,CHANGELOG.mdx,changelog.mdx,LICENSE.md,license.md,
  CODE_OF_CONDUCT.md,code_of_conduct.md` в любой глубине.
- Folder exclusions: `*archive*,*archived*,old,docs/old,*deprecated*,*legacy*,
  *previous*,*outdated*,*superseded*`; `i18n/{zh,es,fr,de,ja,ko,ru,pt,it,ar,hi,tr,
  nl,pl,sv,vi,th}*`; `zh-cn,zh-tw,zh-hk,zh-mo,zh-sg`. Glob matching применяется
  к full path и cumulative folder prefixes; plain names — к каждому folder.
  Поэтому `docs/i18n/ru/a.md` не отвергается `i18n/ru*`, а `i18n/ru/a.md` отвергается
  (если вообще включён). Locale rules GitHub и web существенно разные.
- Nonempty `excludeFiles` / `excludeFolders` **заменяют** соответствующий default,
  не добавляются к нему. Empty lists НЕ отключают defaults. `rules` только metadata,
  не policy evaluator. Config не имеет отдельного include_generated.
- Rank только explicit folder order, затем lexical path. Tree failure fallback
  `README.md` вообще bypasses selection/exclusions; на added refs selection повторяется.

### 2.5 Уже существующий GitHub directory manifest — ДРУГОЙ контракт

`DocsTargetService.resolve_github_directory_target:69–107 →
github_source_manifest.resolve_github_directory_manifest:204 → normalize_resolved`
фиксирует owner/repository/requested_ref/resolved 40-hex commit/directory;
regular files `.md/.mdx`, recursive directory-bound traversal, explicit ceilings,
complete/nontruncated, canonical paths, blob SHA/size и digest.
**Locale/topic/archive/generated-name exclusions GitHubFetcher не применяются.**
Это все format-compatible files разрешённого directory, а не legacy default corpus.

`target_urls:406–432 → library_refresh_ops:149–204 → agent.add(source_manifest=…)
→ WebFetcher._fetch_github_manifest:274–420` fetches exact manifest rows, проверяет
complete/seed match/page limit и file bytes/blob identity; отдельные raw host/path
boundaries. Existing manifest может служить bounded mode ТОЛЬКО для уже approved
directory membership. Не заменять этим legacy repo-wide selection автоматически:
другая membership, suffixes и version semantics. `official=True` не owner consent.

## 3. Technical vs semantic: не blanket removal

| Механизм | Классификация и последствие удаления |
|---|---|
| HTTP(S), credentials, DNS/private IP, redirects, robots, rate/cancel/time/bytes ceilings, segment boundary, hash/blob checks | Technical/security/transport; сохранять. Они не доказывают topic/locale membership или terminal mutation authority. |
| Format suffix/parser/AST/line offsets | Technical representation/supported format; сохранить. Это не тема question. Plain suffix veto без content inspection не абсолютная security guarantee. |
| Web locale list / GitHub i18n/zh rules | Semantic language preference + corpus suppression; удаление включает ранее skipped locale pages. Не protocol exception. |
| blog/changelog/release/status/pricing/settings/search/print veto | Topic/product/presentation selection, не source authorization. Search/print могут быть duplicate/expansion risk, но universal lexical rule не доказывает это. |
| login/signup/register/sign-in/sign-up/account | Safety-oriented account/auth endpoints; не query→answer table, но path words не authentication enforcement. Preserve conservative guard pending separate safety scope decision, не считать blanket semantic whitelist. |
| GitHub legal/changelog names, archive/old/legacy/deprecated words; implicit docs/doc roots и root-file extras | Semantic/default corpus policy. Root-file extras могут расширять explicit folder declaration; removal roots без replacement может обнулить ingestion. |
| Explicit caller paths/patterns/folders/exclusions/ref, declared generated_paths | Source selection inputs; допустимы только как owner-issued concrete scope. Repo-controlled context7 precedence не удостоверяет caller authorization. Не копировать default semantic tables сюда. |
| `utm_*`, fbclid/gclid vs `ref/from/source` | Transport tracking vs unresolved identity-changing strip. Для exact URL contract нужно решение о meaningful params; автоматическое изменение normalization меняет dedup/identity. |

## 4. Реальные caller boundaries: что API уже умеет, чего не гарантирует

- Existing `DocsTarget` / manifest v2 (`manifest_contract:28–68`) содержат URL/
  template, seeds, allowed_domains, path_prefixes, max_pages, format, strategy,
  identity/version/coverage и optional source manifest. Locale/topic allow switch,
  finite-web-membership mode или GitHub file_patterns/folders там нет.
  Persisted query запрещён (`:77–78`); runtime query не source authorization.
- `target_urls:434–453` validates explicit seed/root URLs и rendered version.
  `target_security.path_allowed` uses raw `startswith`, а fetch policy — segment
  boundary. `/docs-other` проходит первый для `/docs`, но не второй. Empty path
  prefixes разрешены; target host helper разрешает subdomains.
- Default MCP `get_docs_context → UnifiedContextService`: allow_network=False,
  prepare_project_docs=False, prefetch_auto=False (`context_tools:293–335`).
  Corpus fetchers не default read lane. Conditional gap LOCAL scanning отдельно.
- Explicit `prepare_docs` targets/manifest/library actions (`prefetch_tools:414–480`)
  вызывают prefetch applications; lifecycle/consent/budget guards не заменяются
  membership. Они не дают новый locale policy по original question.
- **Caller blocker:** non-manifest `DocsPrefetchService:370–446` loops resolved
  URLs separately; passes max_pages/browser/format/query/strategy, НЕ passes
  `allowed_domains,path_prefixes,seed_urls`. Root+seeds здесь не та же операция,
  что в refresh; seed-only target с max_pages=1 всё ещё может выбрать discovery
  candidate вместо supplied HTML URL. Без network audit установлен code edge,
  не доказано реально fetched outside-authorized page в production.
- `library_refresh_ops:180–203` passes allowed_domains/path_prefixes, root+seeds,
  max_pages, strategy и manifest; **не передаёт doc_format/query** в этот `agent.add`.
  Поэтому одинаковый target может иметь разные direct/ranking semantics по caller.
- `inspect_docs_target:205–267` — existing no-discovery exact landing inspection,
  1–5 URLs, one exact host, secure client, no indexing/manifest/browser. Это
  observation/proposal, НЕ уже существующий exact-URL ingestion mode.

## 5. Варианты минимального bounded contract и необходимые полномочия

| Приоритет / вариант | Что owner должен явно разрешить | Точное последствие / ограничение |
|---|---|---|
| P0 caller-boundary prerequisite | Отдельный allocation на prefetch/refresh/agent/fetcher policy propagation, единое interpretation existing fields и tests; network consent не менять | Без этого нельзя обещать одинаковую membership по targets/manifest/refresh. Мой audit не разрешает implementation и не выбирает ABI. |
| P1 finite explicit membership (предпочтительный кандидат, НЕ принятое решение) | Concrete approved URL/file set внутри уже approved host/path/version, finite cap; для старого corpus — проверенный offline source capture либо subset, не generic topic table. Разрешить отдельный exact-membership consumer slice и fail-closed для undeclared pages | Удаление topic/locale heuristics только за этим barrier не расширяет set. Web links/sitemap/nav/llms aggregate не добавляют members; absent set → no fetch/unresolved. Recall сужается, динамические новые страницы не появляются автоматически. Existing web seeds не обеспечивают такой mode; нужен scoped implementation decision. |
| P1 existing immutable GitHub directory mode, только где уже approved | Явное owner/repo/ref/directory authorization и all-markdown membership; подтвердить допустимость каждого resolved set или уже authorized subtree | Можно опираться на existing manifest/commit/blob checks, не context7. Нельзя незаметно менять legacy roots на directory/all markdown: locales/archive/generated и format/versions отличаются. Новый resolution network job требует отдельной authorization, в этом audit запрещён. |
| P2 explicit bounded subtree | Точные host/path/ref и разрешение всех supported-format descendants, включая раньше blocked pages; caps/aggregate acceptance отдельно | Это расширение относительно implicit exclusions для ряда seeds. Допустимо лишь explicit owner-approved изменение corpus; противоречит текущему no-expansion заданию без новой authorization. Никаких automatic parent/sibling/locale/extra-version additions. |
| P3 preserve current legacy membership temporarily | Подтвердить postponement, оставить BLOCKED items и mixed reds | Нулевое production изменение; full exit остаётся NOT DONE. Перенос списков в config не альтернативный exit. |

Необходимые отдельные решения: (1) finite set или subtree; (2) exact requested
version vs mutable ref/extra context7 refs; (3) explicit seed collision/early-return
семантика; (4) full aggregate body допустим или запрещён; (5) canonical/source/
meaningful query identity; (6) direct SDK GitHub/Crawl4AI compatibility: поддержать
новый bounded adapter или fail closed/deprecate, НЕ расширять silently.
Ни одного такого нового API/поля/конфига здесь не вводится.

## 6. Source-map отдельно allocated residual, не corpus unblock

Current `source_map.py` уже не historical version remaining audit:
status_like_tokens всегда `[]`, query stopwords removed, generated NL authorization
removed. Collector и snippets принимают generated только при **`include_generated
is True`** (`:166,238`), `None`/False и explicit path/question этого не меняют.

- `SourceBoundary` (`source_boundary.py:26–179`) читает existing project config:
  source_roots, exclude_paths, generated_paths, include_extensions, gitignore,
  budgets; no symlinks, no outside-root configured roots. include_extensions
  intersect supported suffixes; include_generated не обходит roots/excludes/
  gitignore/tool directories. Empty roots — project root. Built-in archive-v0,
  vendor/tool directory exclusions — separate local corpus/safety policy residual,
  не разрешение убрать remote locale veto. Не смешивать allocations.
- Explicit `include_generated` и `source_boundary` доступны direct SDK
  `build_project_repo_map`, `collect_project_source_facts`, `build_project_source_evidence`.
  `code_context:49` и code_graph collector `:90` их не передают; project/gap callers
  также не открывают generated. В default MCP public include_generated не найден.
- **Suffix-priority residual:** `_source_evidence_terms:402–416` поднимает PascalCase
  identifiers с `Gate|Service|Repository|Controller|Manager|Policy|Adapter` перед
  остальными до cap 16. Это naming-role heuristic, НЕ suffix→language identity,
  не natural-language alias, но влияет на term/snippet budget. LIVE direct snippets
  и supplied requirements; обычный initial MCP source-evidence lane guarded OFF
  (`retrieval_routing:43–68`). Отдельный allocation нужен; не audit B admission fix.
- **Topic fallback residual:** `project_state._documentation_gap_evidence:258–273`
  вызывает repo map с `query or "architecture"`; injected literal влияет на
  positive selection_score (empty query иначе score=0). LIVE conditional
  `create_project_docs_next_action:323` → inspection recommendations
  (`_project_docs_service_part01:510–516`), structured no-docs handoff
  (`project_state:391–392`) и missing-doc query path (`part03:594`).
  Default project context вызывает `inspect_project_docs` (`part01:209–223`),
  поэтому отсутствие query у inspection НЕ делает fallback dormant.
- Отдельный gap capture (`_project_context_service_shared:92–121`) uses collector
  с empty question/include_unmatched=True; suffix priority не исполняется там,
  topic fallback не нужен для этого collector. Он не оправдывает earlier fallback.
  Final public delivery/runtime frequency UNKNOWN; source-span/provenance не
  сертификат NL answer или mutation. AST/import grammar/language map сохранять.

Parent: allocate source-map suffix cleanup и project-state fallback отдельно;
не расширять generated scan ради recall, не подменять fallback новым topic word.

## 7. Offline evidence, actual counts и ограничения

Normal conftest, outbound DNS/socket guard; `PYTHONDONTWRITEBYTECODE=1
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider … -q`.

| Run | Фактический результат |
|---|---|
| `tests/test_dictionary_exit_corpus_policy.py`, `tests/test_dictionary_exit_discovery_literals.py`, `tests/docs/test_source_map.py`, `tests/test_filtering.py`, `tests/test_fetcher_github.py` | **183 PASS / 10 FAIL**, 193 collected; existing assertions неизменны |
| `tests/test_docs_fetch_policy.py`, `tests/test_docs_fetch_transport.py`, `tests/test_web_fetcher.py`, `tests/test_crawl4ai_fetcher.py` | **81 PASS**, 81 collected |

Итого двух непересекающихся runs: **264 PASS / 10 FAIL**, не full CI/quality.
Red nodes: `test_source_map_includes_generated_path_for_explicit_artifact_question`;
filtering `TestInferDocsetRoot::{test_docs_subdomain_collapses_to_host,
test_docs_path_collapses_to_docs_root,test_llms_full_strips_suffix}`;
`TestInferScopePath::{test_deep_path_with_root_hint_widens,
test_deeper_path_with_root_hint,test_reference_root_hint,test_no_root_hint_strips_leaf,
test_api_root_hint}`; `TestIsDocsUrl::test_deep_base_url_widens_scope`.
Это current baseline runs, без overlay/waiver; nine root inference reds и один
removed generated wording authorization red совпадают с recorded mechanism changes.

Также выполнен readonly inline Python без fetch/DNS: **11 printed observations**,
не pytest acceptance/new tests. Parse tree path → `(o,r,v1,docs)`; default selection
на 9 supplied paths → README + docs/a.rst + generated + docs/i18n/ru + docs/ru;
folders=[docs] additionally включает root notes.md; empty exclusion lists ничего
не меняют. Locale first-relative/deeper → False/True; topic seed predicate → False;
query strip → `?a=1`; duplicate llms/seed → llms.txt; suffix terms
`AlphaWidget,BetaService,GammaGate,DeltaProvider` →
`BetaService,GammaGate,AlphaWidget,DeltaProvider`; target/fetch path `/docs-other`
для `/docs` → True/False. Эти observations corroborate static rules, не end-to-end
network reachability и не permission to index новые URLs.

Source-manifest readonly hash comparison: **463/466 совпали**. Две listed
`docmancer/templates/__pycache__/__init__.cpython-{312,313}.pyc` отсутствуют в clean
checkout; local CONTINUE отличается как заранее объявленный handoff. Manifest
не исправлялся. Все остальные listed files совпали; metadata старого manifest
(`1431`, `1476/1`, `13 frozen pins`, smoke PASS, quality FAIL) — historical telemetry,
не результат нового полного запуска. Frozen 13 pins отдельно не rerun; tests/gold/
manifest/threshold не модифицированы. Full rebuilt wheel/MCP/self-host не запускались.

## 8. Dependencies / remaining uncertainties / EXIT gate

- **A identity owner:** findings здесь не implementation audit curated aliases,
  Dart mappings или official-host preference. Перед membership binding нужен его
  exact source identity/version output; concrete URL set не легализует cross-library
  identity. Consumer policy/manifest изменения вне A нужно последовательно allocate.
- **B admission owner:** нет duplicate review lexical/admission implementation.
  Никакая positive literal admission не устанавливает corpus membership, full
  provenance или terminal edit consent. B должен получать реальные bound rows;
  cleanup B не закрывает caller policy propagation или source-map residual.
- Corpus owner/coordinator принимает policy choice и allocation; reviewer после
  завершённого slice проверяет одинаковые targets/prefetch/refresh/CLI/direct SDK
  negatives, seed collision/early exits, locale/topic/extra versions, hash/window
  binding, non-expansion. Existing frozen fixtures/quality floors не менять.
- Unknown: installed-package/external SDK consumers, actual active indexed corpus,
  runtime frequency/final delivery conditional gap paths, all transport/canonical
  attack chains. Static executable edges ≠ runtime trace ≠ full security approval.
  Discovery protocol probes могут иметь transport scope вне member pages; future
  contract обязан разделить discovery requests и admitted document set.
- Existing quality FAIL и mixed reds остаются OPEN. Corpus exclusions BLOCKED до
  explicit decision, source-map suffix/topic fallback — отдельные residual slices.

**FULL EXIT NOT DONE. Никакого implementation decision этим отчётом не принято.**
