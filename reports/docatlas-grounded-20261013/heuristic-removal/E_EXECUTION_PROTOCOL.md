# E — public integration / installed runner handoff

Status: **AUTHORED, NOT RUN**. Worker E performed source/document inventory only;
product/import/test/install/benchmark/model calls **0**. Coordinator alone executes.
No PASS, syntax/import validation, installed behavior or quality gain is claimed.

## Owned files and dependencies

- `tests/test_heuristic_removal_public_integration.py`: two real public scenarios,
  reusing unchanged optics/scope documents/facts and store lifecycle from
  `tests/test_prepared_retrieval_integration.py` / `eval/evidence_quality_v2/runtime.py`.
- `eval/heuristic_removal/{receipts,run,installed_stdio,assess}.py`,
  `config.template.json`, `__init__.py`: E only. No product/oracle changes.
- Runtime Python3.11–3.13/Linux signal deadlines; real doc-atlas, MCP1.x SDK,
  tiktoken0.11.0/o200k_base, YAML; pytest for integration only. No learned model.
- Coordinator central arm selector: `DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL`;
  absent for V0; Q/A/S/ALL literal host values. Old RAS/admission/parents/selector
  experiment flags are cleared, not copied from the previous runner.
- Runtime origin is asserted under selected interpreter prefix and outside checkout.
  The existing fixture module is loaded by explicit file, not a checkout PYTHONPATH.
  Its `patch.dict` isolates host environment only: no storage/retrieval/selection/
  validation/transport replacement. SQL is independent read-only receipt inspection.

## Public boundaries and inventory

| Scenario | prepare/sync | context | resource | model | Boundary |
|---|---:|---:|---:|---:|---|
| E lifecycle |2|7|2|0|public in-process prepare→context→source; real cold store|
| E restrictions |2|6|0|0|public in-process; module/project/exact-version/foreign locator|
| installed smoke |1|2|1|0|installed wheel + SDK stdio; default three-tool surface|
| comparative |per arm/family|<=340|0|0|installed baseline/candidate wheel public in-process dispatcher|

Guards planned **15 contexts total**, within20; outer guards wall240s total,
not240s per command. Stops/failures consume calls and remain visible. Running
existing broad suites in addition is **not** authorized by this inventory.
The existing tests are reused as source fixtures/helpers, not automatically run.

Lifecycle checks exact authored facts after native delivery and common packing,
raw committed snapshot hashes, source membership/line spans/identity/scope,
false answer/edit authority, source resource hash/text, stale rejection, public
confirmed sync/new generation/fresh facts, invalid mutation grant rejection,
logical persistent-state and all project-file equality. Source public
`content_sha256` is **projection fingerprint shape only**, never a claimed raw hash.
Resource and snapshot/raw-file hashes are checked independently.

Trace OFF/ON/OFF: same full public DTO except reissued `source_uri` and its dependent
estimate; actual wrapper calls1/1/1. No product observers, mocks or extra context
requests. This proves public call parity, **not independently instrumented hidden
dispatcher/model call count**. All product behavior still uses real components.

Restrictions use explicitly authored module catalog and supplied exact version;
no inferred lexical scope oracle. Empty foreign-locator/version/missing-module
sources remain hard guards. A source access/integrity violation stops that arm;
read-only violation stops the whole comparative run. Ordinary negative relevance
FAIL does not become an integrity FAIL or retroactively change the oracle.

Installed smoke contains no live corpus/global config/index access. It verifies
wheel import/console origin, calls prepare with finite confirmed source grants,
then context/source and unavailable exact version. stdout/stderr/resource/tool
inventory/native payload and operation ledger retained. Actual client sessions
and production-user smoke remain **NOT RUN/BLOCKED**, not inferred from stdio.

## Fixed comparison design

V0 executes `/tmp/opencode/docatlas-heuristic-removal-baseline-runtime/bin/python`,
pinned base91dd2b4e wheel, not candidate flag-off as an unstated substitute.
VQ/VA/VS/VALL execute
`/tmp/opencode/docatlas-heuristic-removal-runtime/bin/python`, installed frozen
candidate wheel. Origin/prefix failures are setup failures, no fallback to editable.
`BASELINE_WHEEL.json` pins baseline wheel SHA
`d62bb5f7748a2a1bbeadddebf8114a325270775974e9737fa87bbbd2668c6c97`.
Candidate wheel SHA must enter coordinator freeze_files before execution.
Runner additionally checks every installed `docmancer/` wheel member against the
frozen baseline/candidate archive and saves `INSTALLED_ORIGIN.json`; prefix alone
is not treated as proof of the selected build. Final freeze requires a separately
recorded coordinator `code_freeze_manifest` + SHA **before opening D questions**.
Dataset loading hash-verifies D's full independent FREEZE_MANIFEST, including
sealed artifacts, without giving oracle contents to retrieval.

Historical V40 path: `eval/prepared_model_comparison40`; old exposed H20 path:
`/home/viadmin/StudioProjects/hermes/docmancer/reports/docatlas-grounded-20261013/reproduction/eval/prepared_ablation/holdout`.
No historical files/oracles edited. New D20 path passed as JSON configuration;
E has not opened its questions/oracle. **Code freeze first**, D releases public
dataset path/sealed hash to coordinator second, final measurement freeze third.

Design: historical60 × V0/Q/A/S/ALL =300, new20 × V0/ALL =40, total<=340.
Fixed process lane order V0,Q,A,S,ALL, independent cold prepare per lane/family.
This increases explicit preparation counts and has order/cold-start confounding;
not a clean pure-retrieval latency estimate or equal spend. VS is selection+assembly,
not separate effects. ALL is actual Q+A+S, not old RAS. Default baseline and new
qualification/packing may differ by contract; report that, do not disguise parity.

Each context<=60s, prepare<=180s, global comparative engine wall<=1800s;
sequential subprocesses, no retries/repair. Outer coordinator timeout also required.
Started fsynced receipts, including timed-out attempts, are authoritative costs.
Per-arm `SUMMARY.json`, `EXECUTION_LEDGER.jsonl`, preparation snapshots,
`calls/<dataset-index>/<case>/<arm>/{public-payload,metadata,integrity,packed}.json`
and `trace.jsonl` retain raw evidence, wall/CPU/RSS/bytes/token counts/state results.
Root ledger records exact interpreter commands. If outer kill interrupts before
summary, report partial receipts and missing completion explicitly.

Packing is whole native-source ranked prefix, no question/oracle-dependent crop,
full source rows/text/attribution, fixed12000 o200k_base ceiling; native kept separately.
Wire/native tokens and packed tokens are separate spends. Pin offline tokenizer
cache asset/directory in freeze_files; no network download or tokenizer substitution.
No answer generation: model calls0; answer quality/unsupported generated claims
**NOT MEASURED**. Separate label-hidden semantic review still required.

## D interface request (no ownership extension)

Update received before runtime: D has published
`eval/heuristic_removal_holdout/INTERFACE.md`, `source-manifest.json`,
`FREEZE_MANIFEST.json`. E read **only those public interface/manifest files**;
no `sealed/**` contents opened. Runtime adapter now supports D's actual
`sealed/questions.json` plus source-manifest and `corpus/<family>` layout, preserving
original `.rst` locators/bytes. Template dataset3 points to that root. New offline
assessment consumes `sealed/oracle.json` **after freeze**, using
`oracle_schema:D_literal_byte_witness_sets_v1`: all required facts, OR witness sets,
AND byte witnesses; pinned SHA + half-open exact bytes, literal delivered text,
no punctuation/case normalization. Unavailable obligations/forbidden claims are
retained separately, not turned into available coverage. Earlier suggested
historical-compatible schema below is superseded for NEW20, not for old60.

Please publish schema agreement/path/sealed digest via `D_RESEARCH_AND_EVALUATION.md`,
not oracle contents to implementers. Preferred public schema matches historical:
`questions.json: {cases:[{id,project_group,question,answerability}]}`;
`source_plan.json: {families:[{id,paths:[relative-path]}]}` and
`sources/<family>/<path>` pinned UTF8 bytes. Source hashes/commits independently sealed.
Runtime receives only question/root/project scope, never gold or answerability.

Preferred offline `gold_spans.json` uses unchanged historical
`required_claims[].witness_sets[].parts[] {path,line_start,line_end}` alternatives,
`expected_response`, unavailable claims/forbidden inferences. Set config
`oracle_schema: historical_witness_sets_v1` **only after D confirms**. Otherwise
new20 assessment is BLOCKED and D must supply its independent assessor; runner
still accepts public data JSON. Existing `_source_rows` / `_gold` evaluation is reused
verbatim offline, never product helpers, never redefined old oracle semantics.
Exact frozen coverage, strict negative emptiness, integrity, native vs packed,
semantic sufficiency and generated-answer quality remain separate fields.

## Exact coordinator commands (not executed by E)

These are conditional on coordinator replacing the older no-local-runtime
checkpoint prohibition with the explicit experiment authorization, installing the
candidate wheel after code freeze, confirming D interface, and freezing configuration.
Current template intentionally refuses execution (`runtime_authorized:false`).

```sh
# Edit a COPY of config.template.json: real paths, runtime authorization reference,
# wheel/source/oracle/protocol/code-freeze/tokenizer assets, no legacy common flags.
# Freeze hashes only; this does not execute retrieval or parse any gold contents.
/tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -I /tmp/opencode/docatlas-heuristic-removal-20261013/eval/heuristic_removal/run.py --freeze --config /ABS/RUN_CONFIG.json --manifest /ABS/FROZEN_RUN.json

# 13 public in-process guard contexts, no unit/default suite. This pytest command
# is explicitly checkout integration, not installed package origin proof.
# Set TMPDIR to fresh private0700 safe directory so inherited fixture homes satisfy policy.
timeout 240 /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -m pytest tests/test_heuristic_removal_public_integration.py -q --junitxml=/ABS/guards.xml

# 2 installed contexts; execute only within the REMAINING shared guard wall budget.
# Work parent must already be safe/private; sticky /tmp allowed, group-writable
# /tmp/opencode storage parent rejected. No chmod of user/shared ancestors.
timeout 240 /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -I /tmp/opencode/docatlas-heuristic-removal-20261013/eval/heuristic_removal/installed_stdio.py --manifest /ABS/FROZEN_RUN.json --work /SAFE_PRIVATE_PARENT/stdio-work --output /ABS/stdio-receipts --arm ALL --runtime-authorization /ABS/CHECKPOINT.md

# One comparative pass; baseline/candidate interpreters selected from frozen config.
timeout 1800 /tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -I /tmp/opencode/docatlas-heuristic-removal-20261013/eval/heuristic_removal/run.py --manifest /ABS/FROZEN_RUN.json --work /SAFE_PRIVATE_PARENT/comparison-work --output /ABS/comparison-receipts

# Offline only; oracle opens AFTER code/config freeze, never before candidate tuning.
/tmp/opencode/docatlas-heuristic-removal-runtime/bin/python -I /tmp/opencode/docatlas-heuristic-removal-20261013/eval/heuristic_removal/assess.py --manifest /ABS/FROZEN_RUN.json --run-dir /ABS/comparison-receipts --output /ABS/offline-assessment
```

Use an outer coordinator clock across both guard commands; reduce second timeout
to remaining240s. Commands shown separately are not permission to spend480s.
Copy/hash-verify final receipts to permanent primary reports; do not rely on transient
Actions artifacts or a removed worktree. Failures should include exact command,
original stderr and durable started receipt, not a reconstructed PASS.

## Static comparator availability / blockers

Installed package metadata and entrypoint exist at
`/home/viadmin/.npm/_npx/cb869cd955fb8070/node_modules/@arabold/docs-mcp-server/`;
`package.json` says `@arabold/docs-mcp-server`3.2.1, `dist/index.js` present.
Previously pinned node: `/home/viadmin/.nvm/versions/node/v22.22.2/bin/node`.
This is static presence, **not readiness/search quality**. Global Grounded MCP
tool availability is not same-corpus isolation and was not called.

Previous `reproduction/eval/prepared_ablation/comparator.py` has a local CLI adapter
with isolated HOME/config/store, source-file hashes, inventory/null-embedding audit;
its parser bytes are not guaranteed identical to source. It is **not yet safe reusable
as-is** here: `grounded_run.py` passes a Python `no_network.py` path where constructor
expects node; adapter invokes node directly, without that seccomp network boundary.
Do not execute old runner blindly or reinterpret this as an approved20-search run.
Grounded currently **BLOCKED** pending separately frozen safe local adapter and
transport/no-network boundary. No new comparator implementation requested or added.

Remaining blockers: coordinator records D sealed digest in final freeze; candidate wheel hash/installed
origin; real offline tokenizer asset; current explicit runtime checkpoint; coordinator
execution (including syntax/setup findings). If stricter checkpoints preclude local
runtime, route these exact selectors to authorized CI; E does not create workflows.

Ownership extensions needed: **none** for E code as authored. Coordinator owns any
changes to shared `OWNERSHIP.md`, `PROTOCOL.md`, runtime fixture, workflow or packaging;
D owns dataset/oracle/independent semantic evaluator; safe Grounded adapter requires
explicit new ownership assignment before editing its prior files. No delegation.
