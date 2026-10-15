# Finite callers — SECOND disjoint slice

2026-10-07. Worktree `/tmp/opencode/docatlas-final-finite-corpus-42c72bd6`.
Baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
**IMPLEMENTED; independent review/integration required. FULL EXIT / QUALITY / SECURITY ACCEPTANCE NOT CLAIMED.**

## Ownership / extraction

SECOND менял только четыре application production files и добавил tests/shard/report:
**7 files**. `_library_docs_service_part01.py` изменён только для подключения explicit-target
adapter вместо старого target-prefetch callback. `domain/target_security.py` не менялся:
boundary использует существующий segment-aware `DocsFetchPolicy` в дополнение к helper.
Первый 17-file slice, frozen assertions, gold, threshold224, ownership registries и historic
reports не редактировались этим worker. Нет agents, live crawl/HTTP/DNS/index, commit/push,
primary edits. Mocked local indexing выполнялся только внутри offline tests.

В shared worktree появился отдельно выделенный correction slice: его пять production
files НЕ входят в SECOND extraction. FIRST original report SHA256 остаётся
`a7cdcef8e887a366c07044a2c668e9fc513cc11ce06a2bb711a1fc5705b24aee`.
FIRST map отличается только в четырёх payload files, перечисленных correction report;
SECOND их не менял. Original finite tests/shard unchanged. Не извлекать весь shared diff,
`.venv`, correction files или external logs как SECOND.

## Контракт и implementation

- Raw `prefetch_docs` / `refresh_docs` signatures сохранены с optional typed `target: DocsTarget`.
  Без explicit contract — `needs_explicit_target`, до HTTP, регистрации и queue admission.
  Удалены inferred pub/Dartdoc root, Flutter bundles, guessed hosts/robots и resolver fallback.
- Refresh без нового target может mechanically reuse полностью persisted explicit target_spec.
  Нет fallback к record.docs_url, cached resolved_urls или discovery results. Контракт снова
  проходит validation. Library/version/source/raw URL mismatch не расширяет selection.
- Orchestrator принимает один typed target, делает private snapshot, включает SHA256 полного
  selection в request identity (redacted query не может склеить distinct requests).
  Existing consent/confirmation остаются во внешних lanes; неизвестный result не означает healthy.
- Sync/async используют существующие storage writer lease, library lock, staging/atomic publication,
  cancellation/deadline/generation/commit guards. Typed ceilings/controls/manifest сохраняются в registry.
- Per-operation gateway проверяет завершённость каждого ingest и точное множество staged sources
  перед existing commit guard. Partial fetch, stale unselected rows, cancellation, vector failure и
  registry commit failure не публикуют candidate. Previous registry snapshot восстанавливается при failure.
  Existing manifest digest/blob/hash/provenance validation и budget/security guards не обходятся.
- Callable GitHub directory resolver теперь только validates supplied normalized immutable manifest:
  отсутствующий/unresolved manifest — rejection без API; directory authorization не является filelist.
  Package discovery legacy hook metadata-only: возвращает explicit selection без probe/normalization.
- Inspection имеет exact request/redirect binding. Navigation observations не становятся fetch permission;
  indexed/scope_expanded остаются false. Guidance больше не предлагает guessed package replacement URLs.

## Ограничения / parent allocations

1. Это не общий rewrite frozen refresh/prefetch lanes. FIRST refresh staging может содержать старые
   sources; SECOND предотвращает publication через guard, но **не удаляет** эти sources. Replacement
   с лишними active rows требует отдельной allocation/review FIRST refresh/publication machinery.
2. Новый synchronous/async adapter ограничен одним typed target. Multi-target/version expansion и
   legacy raw callers без contract fail closed; это не restoration ради зелёных old tests.
3. FIRST direct target-prefetch lane не получает SECOND gateway guard автоматически. Нужен parent review
   staging/partial-publication semantics всех independently callable lanes; full certification отсутствует.
4. На failure новой библиотеки может остаться pending registry declaration explicit selection; active
   corpus не публикуется. Для existing record восстанавливается previous snapshot. Registry deletion API
   не добавлялся и source identity/lifecycle semantics не переписывались.
5. Full CI/MCP rebuild/frozen-pin acceptance/live corpus/answer quality не выполнялись.

## Offline normal-conftest results

Final combined: **2031 instances: 1948 PASS / 83 FAIL**.

| Selection | PASS | FAIL |
|---|---:|---:|
| All dictionary modules | 1758 | 14 |
| Six technical modules | 76 | 2 |
| Six old mixed modules | 93 | 67 |
| Job executor/service lifecycle | 21 | 0 |
| SECOND callers (included in dictionary): 22 base nodes | 43 | 0 |
| FIRST finite corpus (included) | 64 | 0 |
| Corrections finite corpus (included) | 43 | 0 |

New coverage: docs_url missing rejection; no raw URL authorization; typed caller→Agent→mock secure
transport→local registry/index persistence; exact query/robots forwarding; wrong host/path/ref,
missing controls, unresolved manifests; immutable positive prefetch+refresh; metadata-only package
hook; inspection nonexpansion and redirect query refusal; transport/partial/stale-source rollback;
staged cancellation; commit rollback; vector failure; queue cap/deadline; async snapshot/query identity;
unknown target port result cannot claim healthy. Existing assertions unchanged.

Final command (normal conftest, no cache):

```sh
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_dictionary_exit*.py tests/test_docs_fetch_policy.py tests/test_docs_fetch_transport.py tests/test_github_source_manifest.py tests/docs/test_target_security.py tests/docs/test_content_trust.py tests/docs/test_reference_hash_domains.py tests/test_filtering.py tests/test_fetcher_github.py tests/test_web_fetcher.py tests/test_crawl4ai_fetcher.py tests/test_docs_service_part07.py tests/test_docs_service_part09.py tests/docs/test_library_job_executor.py tests/docs/test_docs_job_service.py -q --junitxml=/tmp/opencode/finite-callers-combined-final.xml
```

Exact 83 red node inventory и traces: `/tmp/opencode/finite-callers-combined-final.log`, final
`FAILED ...` lines; XML содержит каждый instance, classname, name и failure. Эти reds НЕ waived.
Five original dictionary reds и nine additional conflicts сохраняются. Два technical reds:
`test_schema_v1_round_trips_and_plain_github_blob_remains_single_page` и
`test_target_service_resolves_approved_directory_declaration_before_ingest` в
`tests/test_github_source_manifest.py`: ожидают unhashed GitHub/ directory discovery.
Frozen FIRST `test_prefetch_real_agent_path_propagates_exact_urls_and_ceilings` теперь PASS:
persisted explicit contract reuse исправлен без изменения FIRST assertion.
Historic intermediate logs/counts не являются final result.

## Exact payload hashes

| File | SHA256 |
|---|---|
| `docmancer/docs/application/_library_docs_service_part01.py` | `bac6205b48a90fa3aa629a5d80f4d10d16ac6d784c4f130e4ed30d2b66156806` |
| `docmancer/docs/application/_library_docs_service_part02.py` | `27dfb4d029878f6233a43f237098bd20629c74c16ed7d2fc364c8f298dc7b266` |
| `docmancer/docs/application/docs_target_service.py` | `6bc2ac4b3d9ca8936bb0c3d9c6242dda6d3f3060f428efdb48c56e0d0eba7ff7` |
| `docmancer/docs/application/library_ingest_orchestrator.py` | `c3dcb7ce3ca211083e8d917ad24588893b16e9219439967322433fd56ee04f52` |
| `tests/test_dictionary_exit_finite_callers.py` | `edfa4efc11e2286d1163059f678514dc3fa392f71758d1d2983989c091db7d5d` |
| `tests/diagnostic_labels.dictionary_exit_finite_callers.json` | `e278bbb821d807f4055e892b80ed141acc2a06e88b013a475bca261195d4ed96` |

Seventh file: this checkpoint (self-hash separately returned, excluded from map).
Sorted payload map SHA256 (`path + ' ' + hash`, sorted lines, final newline):
`0b28c5ce75c75f2d7190eab8a44f2d4dcc58e045d12cf1695aa9309c9613f756`.
SECOND tracked `git diff --binary -- <four production paths>` SHA256:
`25c855ea138f7be0b4601142b8150914ec38ec37fb565dfafbed8c9baa35087c`.
Tracked SECOND delta: **4 files, 324 insertions / 312 deletions**. New tests/shard/report untracked.
Base-node inventory hash: `9666201a2062d53dfae7e21795566be5a41287e38bd3879a27c0a87ad79c7354`.
Final log SHA256: `64bf0db9c4c66852657d09d0a6c81f41eefc2d4b32f262f1ec9218b865bfe7c1`.
Final XML SHA256: `9ba05be11b5246f2f978a490c667c2023eea182f5d3fb5bc7ac6897820e24ccb`.

Integrate only this 7-file inventory after independent parent review; keep correction slice separate.
