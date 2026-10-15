# Finite corpus — bounded corrective slice

2026-10-07. Worktree `/tmp/opencode/docatlas-final-finite-corpus-42c72bd6`.
Baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
**IMPLEMENTED, NOT INDEPENDENTLY APPROVED. FULL SECURITY / QUALITY / EXIT NOT CLAIMED.**

## Ownership и extraction

Этот correction worker менял только пять выделенных production files:
`docs/finite_membership.py`, `docs/fetch_transport.py`,
`connectors/fetchers/github.py`, `docs/application/docs_prefetch_service.py`,
`docs/application/library_refresh_ops.py` под `docmancer/`.
Добавлены отдельные test module, diagnostic shard и этот checkpoint — **8 files**.
Не переносить общий worktree diff как correction-only diff: caller worker параллельно
менял nonowned application caller files. Ни один такой файл здесь не редактировался.
Extraction ниже — **final whole-file states**, а не diff к first snapshot.

Исходный checkpoint `FINITE_CORPUS_DICTIONARY_EXIT_RU.md` неизменён:
SHA256 `a7cdcef8e887a366c07044a2c668e9fc513cc11ce06a2bb711a1fc5705b24aee`.
Его pins для четырёх изменённых payload files superseded таблицей ниже;
`fetch_transport.py` — пятый production file, отсутствовавший в original 17-file map.
Original tests/shard не менялись:

- `tests/test_dictionary_exit_finite_corpus.py`:
  `f981f5f79af54dc67a203267ef713013d075f9db9a20a112c8573fd219086699`.
- `tests/diagnostic_labels.dictionary_exit_finite_corpus.json`:
  `874be141fd4b8de24e9476f9d573808a3e78c1a0c7b5a89428c7be57fca27e92`.

Нет agents, live HTTP/DNS/crawl/index, commit/push или primary edits.
Новые caller tests используют real Agent → factory → WebFetcher → DocsHttpClient,
`httpx.MockTransport`, mocked public DNS и mocked indexing boundary.

## Исправления

1. `exact_url` отвергает spelling, который HTTPX сериализует иначе: Unicode path/query,
   Unicode/IDNA authority, default-port repair, parser repair и empty query/fragment
   delimiters. Percent-encoded явно выбранные URLs допустимы без query equivalence:
   order, `source/ref/from/utm_*`, значения и trailing slash сохраняются.
   Transport проверяет effective request URL **до dispatch**, включая per-call params
   и client-default params. Прежние два DNS validations, stable-resolution comparison,
   IP pinning, redirect validation и transport limits сохранены.
2. Direct GitHub constructor сразу normalize-ит manifest в новую nested структуру.
   Caller mutation root/rows/digest или wholesale replacement не меняет approved
   source snapshot. Fetch original row работает; extra commit/file seed отвергается
   без HTTP. Commit/blob/SHA256/digest/size и provenance checks не ослаблялись.
3. Prefetch snapshots targets до async handoff; sync также получает private copy.
   Refresh snapshots record и derived target. Shared preflight проверяет весь finite
   target до singleton loop: exact spelling, fragments, technical formats/endpoints,
   explicit selected robots controls, host/path ceilings, DNS/private constraints и
   whole-set page budget. Raw input collection types проверяются до использования
   coerced adapter lists; empty/malformed hosts и malformed prefixes не дают permit.
   Immutable manifest lane сохраняет отдельный blob-to-raw mapping; preflight также
   validates selected raw rows, не делает directory/ref lookup или robots promotion.
   Cancellation/deadline проверяются во время preflight; queue/lifecycle/publication
   machinery не переписывалась.
4. Pure GitHub included-folder utility снова принимает `./docs`, без implicit README,
   root extras, vocabulary exclusions или fetch authorization через globs.

## Проверки (offline, normal conftest)

Environment: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`.
Runner: `.venv/bin/python -m pytest -p no:cacheprovider ... -q`.
Никакие original assertions, gold, thresholds или primary diagnostic manifest
не переписывались. New shard hash проверяется normal conftest.

| Selection | PASS | FAIL |
|---|---:|---:|
| New corrections: 10 base nodes / 43 instances | 43 | 0 |
| Original finite module: 64 instances | 63 | 1 |
| Original six technical suites: 78 instances | 76 | 2 |
| Combined targeted | **182** | **3** |
| All dictionary modules including both finite modules | 1714 | 15 |
| Six old mixed modules | 92 | 68 |
| Combined disjoint selection: 1967 instances | **1882** | **85** |
| Network + dictionary retrieval/selector/projection guards (separate, overlapping selection) | 145 | 0 |

Combined command includes `tests/test_dictionary_exit*.py`,
`tests/test_docs_fetch_policy.py`, `tests/test_docs_fetch_transport.py`,
`tests/test_github_source_manifest.py`, `tests/docs/test_target_security.py`,
`tests/docs/test_content_trust.py`, `tests/docs/test_reference_hash_domains.py`,
`tests/test_filtering.py`, `tests/test_fetcher_github.py`, `tests/test_web_fetcher.py`,
`tests/test_crawl4ai_fetcher.py`, `tests/test_docs_service_part07.py`,
`tests/test_docs_service_part09.py`.
Separate guards: `tests/test_network_guard.py`, `tests/test_dictionary_exit_retrieval.py`,
`tests/test_dictionary_exit_selector_visibility.py`, `tests/test_dictionary_exit_projection.py`.

## Reds / dependencies — не waived

Original five dictionary reds и nine new dictionary conflicts из first checkpoint
остаются. Их literal assertions про vocabulary veto, trailing-slash/tracking
equivalence, unhashed GitHub helper и discovery dispatch не восстанавливались.
Новые correction regressions не требуют переписывания этих assertions.

Три targeted reds в текущем concurrent worktree:

1. Frozen `test_prefetch_real_agent_path_propagates_exact_urls_and_ceilings`:
   nonowned `refresh_docs` wrapper возвращает `needs_explicit_target` для уже
   persisted explicit target и не достигает refresh core. **Parent integration gate**.
   New test отдельно вызывает real `_refresh_record_unlocked` с approved record:
   все selected sources fetch-ятся, extra members не добавляются. Index boundary
   mocked, поэтому ожидается `empty_index`, НЕ claim successful publication.
2. `test_schema_v1_round_trips_and_plain_github_blob_remains_single_page`:
   nonowned target service теперь отвергает unhashed GitHub target.
3. `test_target_service_resolves_approved_directory_declaration_before_ingest`:
   nonowned resolver теперь fail-closed для unresolved manifest.

Mixed failures выросли с 55 до 68 (+13), не declared baseline / не waived.
Additional part07 nodes: restart auto-resume, cancellation during registry commit,
doc_format forwarding, canonical manifest operation `[2]`, manifest corpus replacement,
failed manifest retention. Additional part09 nodes: fresh partial retention,
diagnostic reset, package guidance, project-version lock resolution, latest fallback,
manifest target selection, file-URL rejection diagnostic.
Observed failures include wrapper refusal before queue/agent, new mandatory full-set
preflight stopping fixtures without explicit robots or mocked DNS, and stricter
nonowned source/diagnostic validation. Например manifest corpus replacement stops at
`unregistered outbound DNS blocked: 'github.com'` before FakeAgent. Это не regression
proof для async/rollback lifecycle и не license bypass preflight ради green.
Standalone part07+part09: 24 PASS / 25 FAIL.

Mandatory remaining gate: parent fresh independent reviewer must verify all three
owned blocker fixes AND concurrent caller closure. Inspection unselected redirects,
callable Dartdoc/GitHub discovery and library wrapper selection/forwarding belong to
caller worker (`docs_target_service.py`, `_library_docs_service_part02.py`, orchestrator
and any explicitly allocated support files); здесь они не редактировались и их fixes
не self-approved. Никакого полного security/quality/EXIT или live acceptance claim.

## Final correction payload hashes

Sorted seven-file map `path + " " + sha256`, joined with `\n`, без final newline:
`7efe6658bd9c347b15e3c25900977f3b137f1a23b494853da797048bcc8ea638`.
Checkpoint self hash отдельно в worker return (не recursive self-hash).

| SHA-256 | File |
|---|---|
| `40ee42f49d24d9f19312f989af672d64b4f2264721ff434983c0dc1774641bcc` | `docmancer/docs/finite_membership.py` |
| `596e918da12ff349bf640539cca33f9e86f9c6f20fac363e72eebd5d3d71251d` | `docmancer/docs/fetch_transport.py` |
| `33f1ae1ce66d82fea610aa76497e73ab8fc3d082c1f9badf999b27b2fb1b4122` | `docmancer/connectors/fetchers/github.py` |
| `cfaf0b7de37059334fa569924c66e8061cccda01dde499418859fdfd294404b3` | `docmancer/docs/application/docs_prefetch_service.py` |
| `9d3d0eb439fdfaf2f57ff8fca6895a9150a450ab6df159a2c6654787db108fea` | `docmancer/docs/application/library_refresh_ops.py` |
| `18fa04d624256ccd77c032df3c88723e762eb532bded01b04f874639d44b2bf0` | `tests/test_dictionary_exit_finite_corrections.py` |
| `5b5e1c26ec1c6e8d276b26ddb12a14b7640fa528fffd8ecb1102f987d7161ee0` | `tests/diagnostic_labels.dictionary_exit_finite_corrections.json` |

New 10-node inventory hash:
`2750e3d8dea224b3a71aaecc4aa5ba862ec4e7f08edcc46439ccb426240d7dac`.
