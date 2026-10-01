# Retrieval ablation: isolated T00–T04 project slice

## Итог: development-фаза завершена

**Основной отчёт: [FINAL_REPORT.md](FINAL_REPORT.md).** Production defaults
оставить прежними; экспериментальные replacements не активировать. Расширение
серии остановлено, это не полная T12-приёмка. Поэтапные материалы ниже — история
и доказательства; их «next steps» не являются активным планом.

Completed native-project T06 deliverable: [SAVED_POOL_T06.md](SAVED_POOL_T06.md).
HTML original/canonical adapter: [HTML_PROVENANCE_T05.md](HTML_PROVENANCE_T05.md).
Full-gate paired baseline: [FULL_OFFLINE_GATE.md](FULL_OFFLINE_GATE.md).
Real-P ratio phase separation: [P_RATIO_PHASES_T07.md](P_RATIO_PHASES_T07.md).
Evidence/reader development evaluation: [EVALUATOR_READER_T09_T10.md](EVALUATOR_READER_T09_T10.md).

Latest: [STRUCTURE_T05_REPORT.md](STRUCTURE_T05_REPORT.md). B now measures native
CommonMark source structure; historical FTS-only B is explicitly **B_FTS**.
Production prefix, field weights and gates stay unchanged. D_L additionally
enforces the shared hard-policy allowlist on neighbors. All older reports retain
their original arm definitions; do not combine their B numbers with new B runs.

Current continuation: [CONTINUATION_T07.md](CONTINUATION_T07.md). Applied staging
patches now provide B/D_L/E_G_L; E_GR_L measures a real candidate-ordering pass,
not the whole legacy packing package. Original T05 ownership work remains partial.
The 72-run development replay used ordinary processes, not namespace isolation.

Follow-up: [RATIO_REMOVE_ONE.md](RATIO_REMOVE_ONE.md). `P_MINUS_RATIO` runs the real
P handler with a source-shape-checked, process-local ratio-only hook (missing
parent exact terms retain the original test). 112 repeated development executions
show three answerable wins and an added unanswerable false admission: not grounds
for global removal. Run reviewer with `--planned-arms P P_MINUS_RATIO` for this pair.

Opt-in experiments only. Product code, MCP schema, defaults, `uv.lock`, frozen
protocols/labels and MPNet threshold are unchanged. Original base is
`55637eb4d29a0d06c01714ee647a5b486a5be725`. Historical CI and its two unexplained
head-only failures remain in STAGE_REPORT.md and PAIRED_REGRESSIONS.md; current
continuation evidence is recorded separately in CONTINUATION_REPORT.md.

## What actually runs

**P** invokes the real `language_aware_context.baseline_probe.run` handler and
canonical audit. It keeps product caps and is not resource-matched to A. A
same-call SQL observer preserves actual lists/SQL without another retrieval.
Saturated SQL windows remain incomplete for uncapped recall; no exact first loss
is inferred from them.

**A** invokes native SQLite FTS5 through the existing `_search_rows` frontend,
filter compiler, active-generation joins and field weights `(6, 2, 0.5)`. Each
AND/OR list is independently ascending native BM25. Frozen merge is probe order,
AND before OR, first stable identity—not a global comparable BM25 score. Total
raw exposure is 40 across probes; duplicates consume quota, unused quota is not
refilled. At most 20 unique candidates reach packing. There is no custom ranker,
promotion, expansion, or facet-ordering call.

Before exposure, real metadata/lifecycle/risk rules and mechanical source,
snapshot, hash and span checks run. A complete **explicit unversioned project**
filter additionally enables `ProjectPacketPort`: the actual `SourceReferenceContext`,
reference probe and qualification functions reconstruct owner/source bindings
from the immutable source, not from an injected approval. Headings must match
the parsed source owner. The CLI uses the real project's `project_file` source
class; explicitly indexed `project_doc` fixtures are also supported.

Only the existing `insufficient_visible_match` ratio rejection, with verified
empty missing-exact lists, may be bypassed. Other reference/exact/qualification
rejections stay closed. This is **lexical-ratio-only ablation**, not removal of
all legacy soft gates. Original qualification traces remain private and are not
rewritten to `qualified=True`.

Whole indexed children are packed in rank order using the actual renderer,
snapshot builder and `docs_context_budget_tokens`. Complete DTO limit is 800,
maximum three source entries and two sections per document. Oversized units are
skipped, not cropped. Sources are requalified and the final DTO is validated.
The result is `VALIDATED_PROJECT_PACKET` for this narrow adapter; it grants no
coverage, answer/edit authorization, semantic sufficiency or production support.
The empty result is the real insufficient-evidence DTO. Combined semantic
sufficiency is not evaluated. Library/versioned/incomplete scopes retain
`BLOCKED_SAFE_PACKET_ADAPTER` and cannot be passed to an answerer.

The full-source policy/reference scan is accounted separately in rows and bytes;
it is not free. Current representation, chunks and contextual prefix are not
changed. T05 B, D, E and dense/hybrid are not implemented by this continuation.

## Worker boundary and reuse

CLI P/A run in a Linux user/mount/network/PID namespace, with a private root,
read-only public inputs and staged runtime, writable output/private scratch,
closed inherited file descriptors, clean environment and dropped capabilities.
No host `/proc`, home, `.git`, private labels or semantic reviewer code is mounted.
No namespace capability means `BLOCKED_ENV`; there is no unisolated fallback.
This is a trusted-code research worker, not a hostile multi-tenant sandbox.
Private review data must be outside installed Python/system runtime prefixes.

The existing same-call observer and canonical audit were moved into small
label-free `eval/evidence_quality_v2/public_call.py` and `audit.py` helpers. The
old gate and evaluator retain compatible wrappers/imports; their historical
labels are unchanged. The fixture service imports the same production classes
directly instead of importing an eager gold-loading gate. Only required helper
files and the native adapter are staged—not the evaluation runner or semantic
judge. The worker's staged-code hash and package inventory are saved separately
from the full parent checkout identity.

## Reproduce

Use a full checkout and the unchanged lock. Namespace support must be available;
never weaken the sandbox to clear a guard test.

```sh
uv sync --frozen --extra dev --python 3.12
export DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0
.venv/bin/python -m pytest tests/docs/test_retrieval_ablation_*.py -q
.venv/bin/python -m experiments.retrieval_ablation.run freeze \
  --corpus-dir /absolute/public-corpus --source-manifest /absolute/sources.json \
  --request /absolute/request.json --output /absolute/new-freeze
.venv/bin/python -m experiments.retrieval_ablation.run run \
  --frozen /absolute/new-freeze --arm P --output /absolute/new-P
.venv/bin/python -m experiments.retrieval_ablation.run run \
  --frozen /absolute/new-freeze --arm A --output /absolute/new-A
.venv/bin/python -m experiments.retrieval_ablation.review \
  /absolute/new-P/result.json /absolute/new-A/result.json
.venv/bin/python -m experiments.retrieval_ablation.run regressions \
  --base 55637eb4d29a0d06c01714ee647a5b486a5be725 --head HEAD \
  --output /absolute/new-paired --repeats 2 --timeout 180
```

`regressions` uses the exact two previously failing tests, original conftest and
inventory. Fresh processes alternate base/head order and reuse exactly the same
owned checkout and pytest temp paths. It records target-only and full-collection
conditions separately. `--target-only` is an explicitly narrower diagnostic.
Timeout kills the whole child process group. Missing dependencies and collection
errors are blockers, never passing test results. No failures are waived.

Sources: `{"schema_version":1,"sources":[{"path":"docs/example.md","sha256":"..."}]}`.
Only manifest-listed `.md` bytes and tracked runtime files are staged; untracked
sidecars are excluded. Add new runtime files to the Git index before freezing. Requests accept `question` and
optional fixed `lookup_queries`, never gold or answer hints. Original-only and
frozen-lookup panels remain separate. RST is not relabeled as Markdown.

Freeze captures source/request/protocol bytes, checkout/diff/revision, actual
installed packages, Python/SQLite, flags and lock hash. Outputs are new external
directories. Symlinks, traversal, changed inputs and overwrite are rejected. Code
changes require a **new freeze**; previous results are never silently replayed
under the new protocol. Freeze is not a signature against a party rewriting all
hashes. The worker boundary does not make same-author synthetic cases independent.

## Evidence limits

Guard PASS, packet validity and semantic quality are different measurements.
`review.py` revalidates A's DTO and budget but always reports zero semantic
evaluations here. No answer-model generation, independent holdout, quality gain,
non-inferiority or product simplification is claimed. Full T00–T04 remains limited
by scope, incomplete uncapped traces, and the unresolved full-suite comparison.
