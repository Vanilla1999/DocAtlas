# Stored refresh identity — bounded SECOND correction

2026-10-07. Worktree `/tmp/opencode/docatlas-final-finite-corpus-42c72bd6`.
Baseline `42c72bd6d37700b6fe04890c25e8c4ac45bc9e57`.
**IMPLEMENTED, NOT INDEPENDENTLY APPROVED. Fresh same-reviewer independent review required.**
Полный dictionary exit, security/quality acceptance и integration approval не заявляются.

## Scope / ownership

Ровно **4 final files**: один SECOND production file, новый test module, новый normal-conftest
diagnostic shard и этот checkpoint. Остальные FIRST/corrections/SECOND production files,
existing tests/assertions/shards и historical reports не редактировались. No agents,
live HTTP/DNS/crawl/index, commit/push или primary edits. Local fixture indexing только offline.

Этот report supersedes ТОЛЬКО SECOND pin для
`docmancer/docs/application/_library_docs_service_part02.py`:
old `27dfb4d029878f6233a43f237098bd20629c74c16ed7d2fc364c8f298dc7b266`,
effective **`5a1dcfbab2f26e228a687289bc2af646d956ad9ba955a7c89921f9bbe318fb82`**.
Не переносить общий worktree diff как correction-only diff: остальные slices уже присутствуют.
Production extraction — whole-file effective part02 с prior SECOND implementation и этим correction.
`.venv`, external logs, FIRST/correction payloads и prior SECOND reports исключить из 4-file extraction.

## Reviewer repro / correction

Actual path: `refresh_docs(canonical_id)` → `registry.get` → persisted `target_spec` →
caller rewriting → orchestrator → registry/index. Раньше spec мог заменить record identity:
record `web:finite@v1:api` + spec.version `v2` создавал `web:finite@v2:api`;
spec.source_type `UNKNOWN` / spec.library `other` также могли переключить источник.

Теперь ДО reconstruction, caller rewriting или ingest dispatch:

1. Private deep copy nested spec, без изменения loaded record или caller-owned вложенных структур.
2. Все четыре identity keys должны присутствовать. Каждый component bound к actual loaded
   record.name/ecosystem/version/source_type, не к переписанной caller string.
3. Сравнение использует existing mechanical `normalize_library_name`, `normalize_version`,
   `canonical_library_id`; никаких alias/ecosystem guesses. Field-by-field comparison сохраняет
   source binding даже когда canonical ID без ecosystem не включает source suffix.
4. Blank/nonstring/control-character identity, empty normalized library/ecosystem, malformed version,
   unsupported source отвергаются. Source set взят из existing technical manifest contract:
   api/guides/tutorials/migration/reference/specification; None сохраняет existing API default,
   blank/UNKNOWN не превращаются в default. Loaded record canonical ID также должен совпасть.
5. Missing/mismatched identity возвращает `needs_explicit_target` с точным
   `explicit_target_identity_mismatch`, без compatibility fallback, registration, staging,
   HTTP, queue/job или index mutation.

Valid stored target сохраняет canonical identity и existing exact members, robots controls,
ceilings, nested provenance/identity и manifest. Explicit newly supplied target path, consent /
confirmation, cancellation/deadline, source hashes/version scopes, staging/publication/rollback
не переписывались. Другие consumers и broader identity validation не расширялись.

## Tests / results — normal conftest, offline

Новый module: **3 base nodes / 25 instances, 25 PASS / 0 FAIL**.

- Real caller negatives: library/ecosystem/version/source mismatch, UNKNOWN source,
  blank/punctuation/nonstring/control-character/malformed/missing identity.
  Persisted corrupted spec остаётся неизменным; full temporary-tree source/index/registry bytes,
  jobs, loaded nested record snapshot и selected sources сравниваются до/после rejection.
  Dispatch trap и mocked transport counters подтверждают pre-dispatch/pre-HTTP rejection.
- Valid canonical-ID refresh positive и mechanical case/whitespace normalization positive:
  real caller → Agent → finite fetcher → mock secure transport → local registry/index;
  same canonical identity, exact documents/robots/ceilings и nested identity preserved.
- Separate negative: canonical ID без ecosystem не скрывает source_type mismatch.

| Final selection | PASS | FAIL |
|---|---:|---:|
| New refresh identity | 25 | 0 |
| FIRST finite corpus | 64 | 0 |
| Corrections finite corpus | 43 | 0 |
| SECOND finite callers | 43 | 0 |
| Six technical modules | 76 | 2 |
| **Total: 253 instances** | **251** | **2** |

Точные unwaived reds (existing assertions unchanged):

1. `tests/test_github_source_manifest.py::test_schema_v1_round_trips_and_plain_github_blob_remains_single_page`
2. `tests/test_github_source_manifest.py::test_target_service_resolves_approved_directory_declaration_before_ingest`

Ожидают legacy unhashed GitHub / directory discovery. Correction их не восстанавливает.
Historical 14 dictionary и 67 mixed reds из SECOND report не waived; all-dictionary/mixed/full CI
здесь повторно не выполнялись. Frozen assertions/gold/thresholds не изменялись.

Final command:

```sh
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/test_dictionary_exit_refresh_identity.py tests/test_dictionary_exit_finite_corpus.py tests/test_dictionary_exit_finite_corrections.py tests/test_dictionary_exit_finite_callers.py tests/test_docs_fetch_policy.py tests/test_docs_fetch_transport.py tests/test_github_source_manifest.py tests/docs/test_target_security.py tests/docs/test_content_trust.py tests/docs/test_reference_hash_domains.py -q --junitxml=/tmp/opencode/finite-refresh-identity-final.xml
```

## Exact 4-file inventory / hashes

| File | SHA256 |
|---|---|
| `docmancer/docs/application/_library_docs_service_part02.py` | `5a1dcfbab2f26e228a687289bc2af646d956ad9ba955a7c89921f9bbe318fb82` |
| `tests/test_dictionary_exit_refresh_identity.py` | `bd24166fa480c0cdb4a765b83b4a0d22642bbe276030e0f898546d4c306fd7ac` |
| `tests/diagnostic_labels.dictionary_exit_refresh_identity.json` | `7594b4db1942a27d3c1a7e35766e5a2be5acd89573dc206794898d6387f4df63` |

Fourth file: `v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/FINITE_REFRESH_IDENTITY_CORRECTION_RU.md`.
Checkpoint self-hash отдельно в return; excluded from recursive payload map.
Sorted 3-file `path + ' ' + sha256` map, final newline SHA256:
`18b98bc893bb24703c4878902336ffcc8e8eae3484b59a43974228c7ce80b8aa`.
Base-node inventory SHA256: `4cc3916043911f9c36851523093f348e86c44b41fb919d4505719fe29a4dc503`.

Final log `/tmp/opencode/finite-refresh-identity-final.log` SHA256:
`56f22444b42d9947c4a865151006edcbe8cbc7ba29976c10df4fe76e3c962212`.
Final XML `/tmp/opencode/finite-refresh-identity-final.xml` SHA256:
`d653b0e2b968da82cab8bed1a6318750d274a37dd0b14cb914497a25f532f13e`.

Historical checkpoint pins unchanged:

- FIRST: `a7cdcef8e887a366c07044a2c668e9fc513cc11ce06a2bb711a1fc5705b24aee`
- Corrections: `68cbb080e2722d0da01baf58f309a8690369a22f3575ce737a6d628c2cc7ae09`
- SECOND: `7e4cc142dc33797dad5e43ed4f86dccc655090087f650526cd291d1e98635570`

Remaining mandatory gate: fresh same-reviewer independent check of identity binding and repin,
then parent integration/acceptance. Не self-approve и не claim full exit.
