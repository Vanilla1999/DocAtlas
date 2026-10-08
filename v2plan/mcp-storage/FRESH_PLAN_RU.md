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

### Bounded Linux/macOS finishing pass

User approved Linux/macOS-only product scope and remote macOS verification via
reviewed branch push. This does not authorize merge, publication, live replacement,
historical/evaluation execution or disabling existing required checks.

Three finite owners (one implementation and independent review per slice):

- Active callers: `/tmp/opencode/mcp-final-active-callers`; two previously
  allowlisted active test modules and their own inventory entries. Separate
  eligible-source positives from explicit-rejection negatives; risk labels alone
  neither authorize nor veto bound evidence. Runtime remains unchanged.
- Installer tests: `/tmp/opencode/mcp-final-installer-tests`; only
  `scripts/test-install.sh`. Correct nested OpenCode assertions and verify JSONC
  refusal leaves bytes untouched. Stubbed test execution only.
- Platform proof: `/tmp/opencode/mcp-final-platform-proof`; only new
  `.github/workflows/mcp-platform-proof.yml` and
  `scripts/docs_mcp_platform_proof.sh`. Separate branch-triggered Linux/macOS
  proof, exact wheel/SHA, fresh managed Python and downloaded wheels, no seeded
  runtime dependencies, no source imports, full installed stdio lifecycle.

Existing CI/publish aggregators remain unchanged; this proof does not certify
full required CI or remove Windows from existing policies. macOS architecture
claims require the actual matching runner. Record architecture, wheel hash,
Python, imports and logs, including failure artifacts. Coordinator integrates
only reviewed slices, pushes the exact resulting branch SHA and reports real
remote results. Unexpected defects stop the bounded slice instead of initiating
new architecture or unrestricted test migration.

Independent reviews approved installer `04087e91` and active callers `c9493936`.
Integrated as `8430e1b9` / `59b398d0`. Combined-tree checks: 16 installer checks
and 106 active caller/Python installer tests PASS; scope/syntax/whitespace/D1 PASS.
No production runtime changes. Dedicated platform proof implementation is pending;
no remote result or full required-CI claim yet.

Platform proof `124a60cf` independently APPROVED and integrated as `286d6cfb`:
Ubuntu, macOS 15 ARM64 and macOS 15 Intel standard runners; fresh managed Python,
exact wheel/source SHA, actual installer, full smoke, failure artifacts. Existing
required/publish/Windows gates unchanged. Approved branch push is next; source
review approval is not platform PASS. Inspect the remote run for exact pushed SHA.

### Actual remote Linux/macOS result

First run `37657719513` on `0f02c4bb` failed before installer: redundant
`UV_PYTHON_PREFERENCE=only-managed` conflicted with `--managed-python`. Wheels
built and fresh Python downloads succeeded; no MCP/platform failure inferred.
One-line harness correction `1e9ce4a9` removes only redundant env preference;
managed-only flags and interpreter provenance assertions remain intact.

Run https://github.com/Vanilla1999/DocAtlas/actions/runs/37658168235 succeeded on
exact SHA `1e9ce4a9725cbd9860b2c8b3f6ee364e3ac726d3`. Downloaded artifacts verified:

- Ubuntu: actual x86_64, proof exit 0.
- macOS 15: actual arm64, proof exit 0.
- macOS 15 Intel: actual x86_64, proof exit 0.

Each installed fresh managed Python and downloaded runtime dependencies through
the actual no-build installer, outside-checkout installed imports verified. Full
cold project prepare/retrieve/restart/CAS and both stdio transports PASS. Large
delivery in each transport/platform: 39 372 unique UTF-8 source bytes. Preloaded
library v1/v2 retrieval complete; not remote/library preparation acceptance.
All three independently built wheels have identical SHA256:
`091fd9aadfe0a52dea63dabfd395523923eba9522b3baf48115b27ffaed56896`.
Local artifact copy: `/tmp/opencode/mcp-platform-proof-37658168235-artifacts`.

Linux x86_64 / macOS arm64 + Intel installed-platform acceptance is now verified
for this SHA/artifact. Host uv remains CI infrastructure; uv bootstrap on a
machine without uv is not established by this proof. Full required CI remains
separate/unconfirmed: existing historical/Windows gates unchanged. No PR creation,
merge, tagging, publication or live replacement occurred. Do not rerun matrix
for documentation-only evidence recording.

### Merge finishing checks

Required platform scope `547e1b74` independently APPROVED and integrated as
`bdc32d0b`: ci/platform and p1-stack/platform require Ubuntu, macOS ARM64 + Intel;
all existing steps, aggregators, protected jobs and criteria preserved.
Registration test-only repair `e83d83f9` independently APPROVED and integrated as
`9c7b2e8e`: five complete product modules independently 92 PASS. Nullable schema
and omitted/null docs dispatch, bounded compaction and denied ungranted mutation
remain explicit. Runtime unchanged.

Fetched main/merge-base `d2ed5c4c`; source merge-tree against finishing baseline
`6a27e0d3` clean, no conflicts. Main-relative boundary is 605 files/117 commits
including inherited earlier stages; not a small delivery-only PR. NEXT07 WIP
`0ce30227` belongs to a separate branch, not main or integration ancestry; it is
neither removed nor merged here. PR211 remains old `2d060bf0` until separately
authorized fast-forward of its existing head. Updating it triggers protected
historical/evaluation checks; permission still pending. No full required-CI or
merge-readiness claim and no automatic merge.

### Authorized unchanged PR CI diagnostic

User subsequently authorized updating PR211 and unchanged offline historical /
evaluation execution; external provider calls, live user indexes, publication and
merge remain excluded. Pre-push source audit confirmed automatic self-host
`--live` is provider-free temporary-fixture retrieval, not external inference.
Both remote heads fast-forwarded normally to `b6b13072`; PR211 CI ran on that SHA.

Main CI `37662139596`: installer, static/docs contracts and all three supported
platform smoke jobs PASS. Core 3.11/3.12/3.13, advanced, installed benchmark and
retrieval FAILED; required-ci red. Core diagnostic was incomplete: 3 237 PASS,
1 958 FAIL, 82 ERROR before reporting aborted; 2 787 selected nodes unfinished.
These are not all classified as legacy. Advanced reports 129 FAIL / 493 PASS.

Independent review approved core reporting/member-grant guidance fix `36f9f0a5`,
integrated as `8a806445`: 36 focused PASS, intentional assertion failure exits 1
normally with all filesystem guards restored, no pytest INTERNALERROR. Original
guards/assertions preserved; exact missing-grant denial correctly classified as
authorization, never grants permission. No thresholds or historical artifacts
modified. Retrieval/installed fixture bootstrap slices remain under implementation;
questions, gold/scoring and acquisition cannot be changed to manufacture PASS.
Mass old-ABI/semantic incompatibilities remain open, no full-CI green claim.

Installed fixture repair `f286b71e` independently APPROVED and integrated as
`cdb15b72`. Independent focused tests 11 PASS, contract self-test 7/7 PASS;
unchanged scripted installed task 1/1 PASS at threshold 1.0 with one schema repair,
no infrastructure error/contamination. All 390 installed files/wheel hashes match
reviewed runtime. Questions, oracle, planner, acquisition and scoring unchanged;
only explicit fixture bootstrap/private storage/redacted diagnostics repaired.
Remote outcome for this repair is still pending.

Retrieval fixture repair `b9cde191` awaits independent review. Focused 9 PASS;
one systemic diagnostic completes 80 cases, 0 operational errors/integrity
violations but frozen floor remains red (0/48 sufficient). That run predates
the final dispatcher-binding refinement, so it is not final-commit acceptance;
reviewer will perform one final unchanged diagnostic. No criteria relaxation or
merge-readiness claim from infrastructure repair alone.

Retrieval infra independently APPROVED and integrated as `723ddda5`: focused
9 PASS. Final unchanged 80-case diagnostic exit 1, 0/48 sufficient, no operational
or reported integrity errors. Frozen floors 28/48 and 18/48 unchanged and failed.
Actual acquisition: all 80 retrieved candidates, 804 candidate occurrences,
402 retained spans validated against project/path/source lines, 32 cases with an
originally queried qualified span. All 14 manifest docs matched grants/hashes.
Within primary 48 cases evaluator recognized complete witnesses in 42 indexed /
38 retrieved cases, but all public payloads contained no sources and stopped
before projector with `requires_confirmation=True`, reason `repo_write`.
Not every lost witness is a semantic incompatibility; one finite read-only source
audit is tracing whether docs-gap mutation consent incorrectly vetoes independently
admissible read-only quotes. No bypass, gold injection, criteria rewrite or source
binding fabrication authorized by this observation. Final evidence:
`/tmp/opencode/review-b9cde-systemic-final-20261007-report.json` and `.log`.

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

### Reviewed consent candidate (2026-10-08)

Latest authorization permits agents, normal PR push and unchanged offline
historical/evaluation diagnostics; earlier prohibitions above are historical.
External providers, live user-index replacement, publication and merge remain
excluded. The original /tmp worktrees/evidence disappeared; saved Git commits
were recovered into separate checkouts without changing the user's old checkout.

Independent review APPROVED `1ac550c1`; integrated as `aa153e39` in
`implementation/mcp-ci-reviewed-candidate`. Proposed gap-write consent stays
on the action; authorized read-only quotes are delivered without certifying an
answer or granting edit permission. Genuine preflight/network/source-read and
mutation vetoes remain. Independent final systemic run: 80 cases, 29/48 sufficient
in both lanes, frozen floors 28/48 and 18/48 PASS, no operational/integrity errors,
maximum 798 tokens. Evidence: /tmp/opencode/consent-review-1ac550c1-systemic-report.json.

Bootstrap test update `1d70fba3` independently checked, integrated as `383762d7`:
obsolete blocked/empty-projector assertions replaced by exact retrieval-only,
unverified partial-delivery and source/hash/snapshot checks. No runtime/gold/
threshold change. Combined candidate: 56 infrastructure tests and 5 consent
regressions PASS. Scope ownership records include the two reviewed projection
test paths; D1 catalog and all other checks remain unchanged.

CI triage confirms representative removed max_tokens caller, generated-alias,
risk-label eligibility and retired retrieval_need failures; source-capture setup
also fails without a diagnosed cause. No bulk semantic migration authorized.
The historical core run remains incomplete (2 787 unfinished nodes). Updated
remote CI is needed; this candidate does not establish full-CI or merge readiness.

### Full CI and bounded fixture pilots (2026-10-08)

PR head `aa4dab6c`, CI `37739011872`: retrieval-evidence, installed-mcp-harness,
installer, static/docs contracts and all three platform smokes PASS. Core Python
3.13 completed normally: 2 408 FAIL, 5 610 PASS, 10 skipped, 61 ERROR, 8 089 selected;
no INTERNALERROR. Advanced: 129 FAIL / 493 PASS. Other Python lane counts not
verified. Required CI remains red; later advanced steps skipped after pytest.

Independent review APPROVED fixture pilot `fcd6b990`, integrated as `47280ab1`:
two capture failures closed through confirmed finite preparation and pytest
lifecycle cleanup. Both modules baseline 3 PASS / 7 FAIL, candidate 5 PASS / 5 FAIL.
All 53 test assertions, catalog/corpus writes and questions preserved. Environment,
home/global cleanup verified on normal execution and injected failures. Four
remaining failures reproduce on baseline; public-handler empty read_next is newly
exposed after preparation and not established as baseline. Assertion retained.

Independent review APPROVED `d684791e`, integrated as `f8427bb5`: only unused
max_tokens keyword removed from validation test stub. Baseline 10 PASS / 1 FAIL,
candidate 11 PASS. Original three assertions and protocol budget 2000 unchanged.
These local pilots do not replace full CI or authorize semantic migrations.

### Reviewed recovery-test migration (2026-10-08)

Independent review APPROVED `0af97d0b` plus `f579ebd7`, integrated as `624fcbdb`
and `506d9e0a`. Complete-window delivery verifies exact admitted quotes and empty
read_next. Separate real public preparation/retrieval/source-read fixture quotes
lines 1–11 and registers unread lines 12–25, checking bytes and snapshot binding.
Reviewer caught invalid-catalog revocation false positive; follow-up now validates
active historical/search_only catalog before genuine authority/binding denial.
No production, schema, gold, thresholds or budgets changed. Diagnostic inventory
updated only for migrated nodes; ownership records include its reviewed shard.
Integrated infrastructure, validation, capture and migrated recovery tests:
74 PASS. Four independently confirmed baseline recovery failures remain outside
this approval. Required CI must be rerun; no full-CI-green or merge claim.
