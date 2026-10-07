# Свежий план завершения MCP

Integration base: `70d2553c`; packing base: `b8547099` (ещё не интегрирован).

## Явные решения пользователя

1. Автоустановка: installer скачивает подходящий Python и готовые зависимости.
   Это выбор способа поставки, не команда на live reinstall/config replacement.
2. Локальный MCP с trusted storage вне проекта, обычный SQLite. ОС и процессы
   текущего пользователя считаются доверенными; защита от malicious same-UID
   процессов в этот профиль не входит. Это явно согласованная смена storage
   threat model, не утверждение, что VFS закрыл прежний R1.
3. Недоверенные документы, запросы и проектные пути по-прежнему проходят
   grants/scope/hash/span/source-read проверки. Нет новых authority из metadata,
   ослабления validators, semantic dictionaries или искусственных weights.
4. Старую БД сохранять/мигрировать не нужно. На этом этапе она не читается и
   не удаляется; initialization и lifecycle проверяются на isolated fixtures.

## Что обнаружила свежая проверка

- Native VFS не решает неограниченное same-UID вмешательство; production его
  не использует. Spike остаётся experimental evidence старых ограничений.
- Prepare hardcodes project-local storage, обычный runtime может выбрать app-home
  DB или project config. Нужен один trusted target для initialize/prepare/retrieve.
- Packing tests обходили реальные `LibraryDocsService` forwarders. В production
  graph ACK отклоняет легитимное делегирование. Второй дефект — deepcopy даже
  при выключенном retention. 298 PASS не покрывали эти два пути.
- Remote PR #211 по-прежнему на `2d060bf0`, OPEN, CI красный на том старом SHA.
  Это не результат проверки текущего локального integration tree.

## Владельцы и конечные результаты

### A — trusted storage lifecycle

Worktree `/tmp/opencode/mcp-fresh-storage`, base `70d2553c`.
Точный allowlist:

```text
docmancer/core/member_storage_policy.py
docmancer/core/_sqlite_store_part01.py
docmancer/core/config_resolution.py
docmancer/docs/application/project_docs_member_transaction.py
docmancer/docs/application/_project_docs_service_part01.py
docmancer/docs/application/_project_docs_service_part02.py
docmancer/mcp/_docs_server_part01.py
docmancer/docs/interfaces/mcp/prefetch_tools.py
docmancer/mcp/_docs_server_tool_data.py
tests/test_mcp_delivery_member_transaction.py
tests/test_mcp_delivery_dispatch_boundary.py
tests/diagnostic_labels.mcp_delivery_member_transaction.json
tests/diagnostic_labels.mcp_delivery_dispatch.json
tests/test_mcp_trusted_storage_lifecycle.py
tests/diagnostic_labels.mcp_trusted_storage_lifecycle.json
```

Один host-selected storage target вне проекта; caller/project config не выбирают
другую БД. Явная confirmed initialization только отсутствующего хранилища;
unexpected existing DB не adopt/overwrite. Early grant validation до mutation.
Generation CAS и member ownership в одной SQLite transaction. Retrieval/restart
используют тот же target. No orphan deletion, vectors, extraction publication.
Существующие source FD/budget/hash checks сохраняются. Initial journal route —
rollback; никаких claims о защите от same-UID или hostile journal destruction.

A completed `0ee73213`, independent storage R review pending. Default target:
`$DOCATLAS_HOME/mcp-members/members.db`. Existing confirmed mutation with explicit
null generation provisions only an absent target after source validation. A
reports 168 focused PASS and actual source-stdio cold prepare/retrieve/restart in
both transports; not installed-wheel acceptance. One workflow schema test still
expects the superseded project-local target; coordinator will migrate that test
after review. Private app-home namespace required; group-writable `/tmp/opencode`
is not an accepted storage root. No live DB/config/install change.

Independent storage R APPROVE integration (trusted-local profile): 168 + 7
focused checks PASS. Storage включён как `1c505516`. Coordinator обновил один
устаревший schema-description test и source-runtime fixture `PYTHONPATH`, чтобы
дочерние процессы после chdir не импортировали другой editable checkout.
Combined source storage/packing/installer rerun: 478 PASS. Source fixture path
не применяется к installed-wheel acceptance; это разные evidence lanes.

### B — минимальный packing repair

Worktree `/tmp/opencode/mcp-fresh-packing`, base `b8547099`.
Точный repair allowlist:

```text
docmancer/docs/domain/project_doc_ranking.py
docmancer/docs/service.py
tests/test_action_packet_v4_found_window_retention.py
tests/diagnostic_labels.action_packet_v4_found_window_retention.json
```

Bypass ACK/signature/deepcopy в обычном режиме; два настоящих forwarders получают
корректное child delegation. Новый ACK/capture framework не разрабатывается.
Проверка реального service graph и actual lexical retrieval на временной БД,
плюс прежние security/qualification/acquisition-trace tests.

B repair завершён: `a2df42fded4d555ac3b70185b91a2064a1f7ae91`.
По отчёту B 302 full focused tests PASS. Real temporary SQLite / lexical /
production graph / public handler: 45 qualified windows, 32 475 source bytes
(не >32 KiB). IDs/text/hashes/spans fidelity и acquisition/source-read traces
совпадают с docs mode. Fresh independent R review запущен; до verdict весь
packing series остаётся вне integration branch.

Independent packing R APPROVE integration: 302 matrix + 19 diagnostic/support
tests PASS; real lexical proof отдельно PASS. Series включена в integration
`28e15d55` (`6daa0fe2`, `362cfbae`, `eda9db59`, `28e15d55`). Итоговый rerun с
installer: 326 PASS; scope/syntax/whitespace/D1/line-budget PASS. Это закрывает
scoped packing findings, но не installed >32 KiB, storage lifecycle или release.

### C — lineage и installed acceptance

Свежий audit выделил минимальный lineage fix: canonical индекс уже хранит
original text/hash/IDs/spans/generation; presentation cleaning теряет их.
C implementation approved в `/tmp/opencode/mcp-fresh-delivery`, base `f8be0e7c`:

```text
docmancer/docs/application/_library_docs_service_part03.py
docmancer/docs/application/_unified_context_service_part02.py
scripts/docs_mcp_stdio_smoke.py
tests/test_docs_mcp_stdio_delivery.py
tests/diagnostic_labels.mcp_delivery_c.json
```

Carrier transport не даёт permissions; missing/conflicting/transformed lineage
reject, hashes/spans не выдумываются и не наследуются cleaned snippets.
Original source text остаётся bound к existing canonical producer fields.
Installer node hash в shared shard сохраняется. Exact version ожидается как
`version_binding="exact_snapshot"` плюс numeric resolved-version binding.
>32 KiB — один natural multi-document fixture attempt под прежним acquisition,
с отдельным учётом acquired/qualified/returned unique spans. Нет padding,
acquisition expansion или засчитывания wire bytes как source bytes.

C source-level real public-route fixture: 39 372 unique UTF-8 bytes, 50 windows,
complete, unchanged acquisition; не installed lifecycle acceptance. C green
commit held на двух обнаруженных wire contracts: numeric `resolved_version`
теряется в packet reconstruction; nullable context format удаляется sanitizer.
Delivery 34 PASS / 3 FAIL, v4 regression 114 PASS, installer 24 PASS по отчёту C.

Отдельный D contract repair worktree `/tmp/opencode/mcp-wire-contract-repair`,
base `1c505516`, exact allowlist:

```text
docmancer/docs/application/_action_packet_shared.py
docmancer/docs/application/_action_packet_part03.py
docmancer/docs/application/_action_packet_part04.py
docmancer/docs/interfaces/host_context.py
docmancer/mcp/_docs_server_shared.py
tests/test_action_packet_v4_wire_version.py
tests/diagnostic_labels.action_packet_v4_wire_version.json
```

Resolved version переносится только из existing producer binding, не request.
Missing/contradictory bindings остаются unresolved/rejected; validators не
ослабляются. Nullable schema honoring не разрешает null в не-nullable fields.
C/D имеют непересекающиеся owners; integration после independent review.

D `e6d462ed` готов, independent review pending. Coordinator мигрировал ровно
`tests/docs/test_host_scope_planning_contract.py` с superseded prose-routing
policy keys на explicit scope/no-widening contract; вместе с workflow schema
42 tests PASS. Дополнительно выполненный active `test_host_scope_contract.py`
имеет 13 existing migration failures: obsolete onboarding guidance и legacy
ingest без mutation grant/catalog. Это отдельный active-CI backlog; assertions
не отключены, runtime implicit-ingest/prose policies ради зелёного не возвращаем.

Independent C R REQUEST CHANGES на `e5cb1fce`: повторные `(source, stable_chunk_id)`
admitted на producer/consumer уровнях, включая identical duplicates и conflicting
parents с matching carriers. Counterexamples independently reproduced на real
SQLite fixtures; C получил finite fix: reject все rows repeated identity до
admission, не выбирать произвольного winner. Остальные lineage/smoke boundaries
по source audit корректны; R не воспроизвёл весь C matrix из-за доступных deps,
не заявил closure D/installed acceptance. C integration HELD до duplicate fix.

Bounded active-scope migration: `/tmp/opencode/mcp-active-scope-tests`, base
`33390ee5`, только `tests/docs/test_host_scope_contract.py` и его active shard
`tests/diagnostic_labels.scope_span.json` при необходимости. 13 failures
мигрируются на explicit catalog/grant/prepare в isolated app-home, не SQL
bootstrap/implicit ingestion. Все scope/foreign isolation assertions сохраняются.
Runtime prose classification, historical artifacts и gates не меняются.

Independent D R APPROVE integration: 316 PASS / 1 obsolete workflow wording
failure, уже исправленный на main. Strict optional string `resolved_version`,
nullable enum honoring и отсутствие request-derived version synthesis проверены.
D integrated `7a5b87d3`; combined wire/packing/lifecycle/scope rerun 351 PASS,
scope/D1/syntax/whitespace PASS. C получил approved dependency handoff; duplicate
finding по-прежнему требует отдельного closure/review, не закрывается D.

C followup `853d39e8` atop `e5cb1fce`, с approved D dependency, tested HEAD
`f6c1455f`: по отчёту C 332 tests PASS (193 delivery/wire/v4/installer +139
trusted lifecycle/member). Три D-related failures resolved. Independent C R
повторяет duplicate counterexamples и green matrix; integration до verdict held.
Installed-wheel matrix ещё не запускалась.

Active scope migration `cc1376ff`: один test module, base node hash сохранён,
155 active PASS по отчёту агента. Все пять isolation assertions сохранены,
root/foreign positive controls добавлены. Independent review pending. Expanded
run нашёл 25 untouched obsolete NL/proof failures; full CI green не заявляется.

Coordinator подготовил isolated wheel runtime с existing Python 3.12 deps без
`.pth` и без `docmancer` из seed: `/tmp/opencode/mcp-integrated-wheel-if9p586h`.
Пакет ещё не установлен, smoke не запущен; нужен approved integrated C SHA.

C independently APPROVED и интегрирован как `4f047c0b` / `98c1544e`;
active scope migration independently APPROVED и включена как `3636ebd9`.
Coordinator включил identical large probe в text transport (ранее NOT RUN)
и сохранил strict nullable scope enum assertion после D. Combined matrix:
542 PASS; scope/D1/syntax/whitespace/line-budget PASS. Installed smoke следующий
gate; ни source >32 KiB, ни эти tests не заменяют artifact acceptance.

## Installed artifact — coordinator result

Runtime SHA: `b9f52004`. Wheel `doc_atlas-1.3.2-py3-none-any.whl`, SHA256:
`091fd9aadfe0a52dea63dabfd395523923eba9522b3baf48115b27ffaed56896`.
Artifact/runtime directory: `/tmp/opencode/mcp-integrated-wheel-if9p586h`.

Wheel built from integration, installed offline without source checkout / `.pth`
in an isolated Python 3.12.3 runtime. Existing seed dependencies copied: this is
not clean-machine auto-install proof. Verified module location is that runtime's
`site-packages/docmancer`, not editable/source imports. `PYTHONPATH` removed;
execution outside checkout. Full stdio smoke exit 0.

Structured **and text** observations:

- Real cold confirmed prepare → retrieve, no project-index fixture bootstrap.
- Process restart/repeat/CAS checks PASS; repeat writes 0, stale null rejected.
- Omitted/null docs mode, complete/partial evidence and scope/version isolation
  observed; missing module/version stays unavailable.
- Large delivery: 50 windows, **39 372 unique UTF-8 source bytes**, complete,
  in each transport. Wire bytes and duplicate spans not counted as source bytes.
- Authored library v1/v2 sources deliver exact version-bound evidence. Library
  indexes are explicitly preloaded after cold project acceptance: this proves
  library retrieval/lineage, not remote/library preparation lifecycle.

Fresh app storage is private temporary state under the user home, not live
storage. Same-UID interference protection is outside the approved trusted profile.
No source/hash/span/authority validator relaxation or provider/index expansion.

Independent artifact R repeat/log review is running. Remaining gates: full active
CI migration (known untouched NL/proof expectations), clean auto-install and
platform coverage, then separately authorized push/release/live replacement.
Package remains 1.3.2: no release version or deployed parity claim.

## Independent installed approval

R APPROVE scoped installed acceptance: independent full smoke exit 0,
Python 3.12.3, no source `PYTHONPATH`, outside checkout. Both transports cold
project lifecycle/restart/CAS/scope/version/default-null/partial-complete PASS;
large each 39 372 unique bytes / 50 windows / complete. All 390 wheel Python
modules match runtime `b9f52004` and installed files; D1/module/diff gates PASS.
Wheel SHA256 unchanged. Evidence:

```text
/tmp/opencode/mcp-integrated-wheel-if9p586h/independent-installed-smoke.log
/tmp/opencode/mcp-integrated-wheel-if9p586h/independent-installed-evidence.json
```

Functional project lifecycle/delivery is accepted for this profile/artifact.
Seeded dependencies are not clean auto-install proof; preloaded library retrieval
is not remote/library preparation acceptance. Full active CI and Windows/macOS
coverage remain unproved; 25 reported obsolete NL/proof failures pending explicit
active-test migration. Release/deployed parity remains unclaimed.

## Real installer check (separate evidence lane)

Coordinator started actual installer in isolated fresh tool/bin/config/home dirs:
`/tmp/opencode/mcp-auto-install-5eo4yg8f`, registration `none`, exact built wheel,
no dependency copying, managed Python selected, new source builds disabled.
Offline attempt exited 1: required `fastembed==0.8.0` missing from cache; no
fallback/registration occurred. Network attempt exited 0: 83 declared package
dependencies resolved/installed, no copying from the seed and no new source build.
Existing managed Python/uv are reused: neither attempt proves clean-machine uv /
Python bootstrap, and no existing live MCP/tool directories are replaced.

First post-install import probe executed from checkout and resolved source: it
is explicitly invalid as installed-import proof. Corrected isolated probe and
full smoke run outside checkout, no `PYTHONPATH`, import from fresh tool env
`site-packages/docmancer`; full smoke exit 0 with downloaded dependencies.
Both transports large 39 372 unique bytes, library v1/v2 complete. Evidence:

```text
/tmp/opencode/mcp-auto-install-5eo4yg8f/installer-network.log
/tmp/opencode/mcp-auto-install-5eo4yg8f/fresh-dependency-smoke.log
/tmp/opencode/mcp-auto-install-5eo4yg8f/fresh-dependency-evidence.json
```

## Remaining active NL/proof unit batch

Approved implementation in `/tmp/opencode/mcp-active-nl-contract-tests`, base
`6e18862b`, exactly:

```text
tests/docs/test_query_planning_scope_regressions.py
tests/diagnostic_labels.query_planning.json
tests/docs/test_quantified_attribute_scope_isolation.py
tests/diagnostic_labels.quantified_attribute_scope_isolation.json
```

25 existing failures reproduced on updated main, all in offline core CI; bounded
batch only, not full-CI inventory. Tests migrate to explicit finite requirements,
immutable question/conditions and exact source hash/span witnesses. Positive and
negative controls preserved; no semantic-entailment certification, runtime NL
classifier/weights, permission from completeness or historical changes. Query
shard's other three modules remain untouched. Independent review before integration.

Batch implemented as `5f282a57`: four files only, no runtime/helper changes.
Baseline 25 FAIL → 25 PASS; wider approved active batch 156 PASS по отчёту агента.
All original scenarios retained as explicit mandatory requirements with positive
command/inventory/path/number witnesses and negative stale/foreign/forged-span /
changed-rehashed-text controls. Independent semantic assertion review pending;
not full CI or semantic-entailment certification.

Coordinator default offline-core COLLECT-ONLY: exit 0, 8 063 selected / 622
deselected / 8 685 total, inventory gates PASS; none executed. Log:
`/tmp/opencode/mcp-integrated-wheel-if9p586h/active-core-collection.log`.
Read-only CI source audit separates protected mixed historical/evaluation nodes
before any broader execution; excludes must be justified by protected scope,
not failures. A full core run is not authorized by collection success alone.

Independent R APPROVE `5f282a57` unit migration: focused 25 PASS / approved wider
156 PASS. Integrated as `2083c4c1`; main rerun across migrated unit/scope/v4/wire /
delivery/trusted-lifecycle modules: 239 PASS. Scope/D1/syntax/whitespace/line-budget
PASS. Other legacy modules still fail in a different selection; no full-CI claim.
This batch does not change runtime `b9f52004` or previously verified wheel code.
Финальное доказательство — установленный wheel, настоящие stdio structured/text,
fresh initialization → prepare → retrieve → restart, а не fixture bootstrap.

### Coordinator / R

Coordinator фиксирует interfaces/ownership и интегрирует проверенные commits.
Coordinator installer paths: `scripts/install.sh`,
`tests/test_opencode_v2_installer.py`, installer module hash в
`tests/diagnostic_labels.mcp_delivery_c.json`. Installer теперь запрашивает uv
managed Python (default 3.13, overrides 3.11/3.12/3.13) и `--no-build`:
при отсутствии wheel fail, без compiler/source fallback. 46 focused installer /
agent-config tests PASS; это stubbed installer проверка, не clean network install.
Шард C далее передаётся C: installer hash нужно сохранить, изменяя только
delivery module inventory для его новых тестов.
Independent installer R одобрил scoped change: 46 tests PASS, uv 0.9.25 syntax
подтверждён. `--no-build` допускает reuse cached built wheels; не authentication
origin guarantee. Clean install / universal platform wheels ещё не доказаны.
Coordinator также владеет ровно installer paragraph в `README.md` для docs drift.
R независимо проверяет итоговые изменения и реальные acceptance paths.
Без nested agents и пересекающихся владельцев файлов. Общий runtime release
проверяется на одном integration SHA; broad native/capture redesign остановлен.

## Условия завершения

- Реальный fresh lifecycle и scope/version/partial evidence проходят validators.
- Library lineage сохраняется от producer; hashes/spans не синтезируются ради PASS.
- >32 KiB считаются только по уникальным source bytes в одном реальном ответе;
  если acquisition не даёт их, ограничение отчётливо фиксируется, guards не растут.
- Active CI contracts мигрируются без изменения historical gold/thresholds и
  отключения gates. Historical evaluation suites не запускаются.
- Auto-install проверяется на clean supported environments без компилятора;
  текущий shell installer пока поддерживает Linux/macOS, Windows требует своей
  проверенной installation route. Версия runtime/release отдельно фиксируется.
- Live replacement, push/merge/publish и удаление старой БД остаются отдельными
  действиями. Одна MCP registration с сохранением существующего имени.
