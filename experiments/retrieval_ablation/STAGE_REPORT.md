# T00–T04 stage report

Base: `55637eb4d29a0d06c01714ee647a5b486a5be725` (current main at start;
PR #204 was already merged). Branch: `experiment/retrieval-ablation-t00-t04`.
Implementation: `d60a9c0d3eb279858c0ab41913eaf6ac7097f2f0`.
Reviewed code: `00e83b1334c883cea8f6c2b3512cdd00ee92a1c9`.
Documentation added after the measured code does not alter the runtime.

## Stage disposition

| Stage | Result and limit |
|---|---|
| T00 | Full Git history was recovered through a credential-free CI bundle after local Git DNS failed. Local frozen dependency sync was blocked by an uncached onnxruntime wheel; CI installed the unchanged lock and executed the real handler. Environments are recorded separately, not claimed identical across local and CI. |
| T01 | Real P handler, audit and contract token counter execute. The new raw SQL observer and existing observer preserve complete DTO, SQL/parameters, ordering and index bytes on the supported synthetic Markdown fixture. Original SQL caps remain; uncapped recall and exact first loss are not established. |
| T02 | PARTIAL. Real source/project/version-filter/lifecycle/risk gates and mechanical snapshot/quote guards are used for internal A candidates. Complete shared final packet and reference/authority adapter is BLOCKED_SAFE_PACKET_ADAPTER. |
| T03 | PARTIAL. Exact request/source/protocol/runtime freeze, manifest allowlist, traversal/symlink/overwrite checks, flags and missing-arm reporting are implemented. OS-enforced gold isolation and an independently frozen quality dataset are not implemented. |
| T04 | Native FTS scorer diagnostic implemented and exercised against real tables/active generation/filter compiler. No custom ranker/expansion/packet is called. A's whole-unit public packet remains blocked, not simulated. |

Overall: useful diagnostic slice, **not completion of every T00–T04 criterion**.
T05–T12, new dense models, B/D/E, real answer generation and product simplification
are not part of this delivered slice.

## TDD record

The initial adapter that simply delegated to `_search_rows` failed a behavioral
assertion: `16 <= 4` was false. One per-probe quota shared by actual AND/OR SQL
calls made the same assertion pass. No import or collection error was called RED.
Source-policy/native-order tests were baseline-green checks against the reused
real components; they were not deliberately broken.

Review then produced real failing assertions for manifest symlinks (1), unearned
quality/holdout promotion (1), changing frozen runtime flags (3 parameterized
cases), and missing-arm planned counts (1). All were corrected and rerun.
`obsolete` was an invalid lifecycle fixture value; it was replaced with the
real supported `superseded` state without changing production rules.

## Actual executions

Completed CI run [36781801281](https://github.com/Vanilla1999/DocAtlas/actions/runs/36781801281)
executed code `00e83b1334c883cea8f6c2b3512cdd00ee92a1c9` and ended **FAILURE**.
The artifact was downloaded and its archive SHA-256 verified:
`6495372806fcda3ce8ffeb915fb2aa43f9201855f3af3530d9f8dff7f660c222`.
Python was 3.12.14, SQLite 3.45.1; the complete package inventory is retained.

| Execution | Base | Head | Interpretation |
|---|---|---|---|
| New guards plus existing SQLite tests | — | 74 passed | Includes both real-handler tests; 51 new and 23 existing cases. |
| Focused product suite | 482 passed, 1 failed | 482 passed, 1 failed | Same 483 IDs; same failed assertion, raw failure messages differ in generator address. |
| Full offline suite | 5,048 passed, 20 failed, 10 skipped | 5,097 passed, 22 failed, 10 skipped | 5,078 common IDs; 51 added tests passed; 2 existing cases passed on base and failed on head. |
| Frozen P / A smoke | — | 2 EXECUTED | One synthetic English Markdown case, zero semantic evaluations. |

Both full offline invocations also deselected 622 advanced/live cases. No
existing IDs disappeared. All four focused/offline commands exited 1; those
failures were not suppressed. The complete testcase comparison is retained in
`paired-comparison.json`; human review is in PAIRED_REGRESSIONS.md.

The two new head-only failures are **open blockers**, not proven flaky and not
proven caused by this patch. Product source bytes are unchanged, but that alone
does not prove absence of test-collection, ordering, path or runtime effects.
There has been no isolated repeat that establishes their cause. Two previously
failing full-suite cases also have changed observable failure content; these are
reported separately rather than hidden in equal/near-equal totals.

The earlier implementation CI on `d60a9c0d` is not substituted for the completed
reviewed-code run. Reports originally recorded the in-progress state; this
revision replaces it with downloaded final JUnit and packet evidence.

Local commands used `DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0`:

```sh
python -m pytest tests/docs/test_retrieval_ablation_contract.py \
  tests/docs/test_retrieval_ablation_integration.py \
  tests/test_sqlite_ranking_truth.py tests/test_sqlite_phrase_ranking.py \
  -k 'not public_handler' -q
```

Local Python 3.13.5 / SQLite 3.46.1: **72 passed, 2 deselected**. The two full
handler tests were deliberately not run in this incomplete local environment;
CI runs them with locked dependencies. Separate base/head native product tests
were **23 passed / 23 passed** on identical test IDs in the same local runtime.
These overlap the tests above and are not additional independent quality cases.

CI uses `uv==0.9.25`, `uv sync --frozen --extra dev`, Python 3.12, offline retrieval,
automatic vectors disabled, zero hash seed, and the unchanged diagnostic inventory
hooks. The focused suite uses the existing `flow_regressions --condition baseline`
module list in both worktrees. Full offline command in each worktree:

```sh
python -m pytest tests/ -m 'not advanced and not live and not live_network' -q
```

The workflow preserved actual exit status and uploaded raw JUnit, logs, original
packets, SQL lists, frozen inputs, package inventory and source bundle outside
Git. Those artifacts were downloaded and inspected. The delivery archive includes
their evidence files (excluding the large Git bundle), local RED/GREEN logs,
72-test JUnit and the separate 23/23 native product comparison.

## Identity and unchanged boundaries

`uv.lock` SHA-256:
`c0f6d716e8ec5e442dc707995c134a152bc37122bf1a9217b020f86db80447ec`.
Real FTS producer `_sqlite_store_part03.py` SHA-256:
`e504fdad421cc1cd11fe15330e08b904487f8229ffe1af472fde928199572dd5`.
Real evidence policy module SHA-256:
`76426154516c9454942b7833c73060121c146b392602b5d6882e1206fdc6f4f1`.

Only the new experiment, its tests/label shard and its narrowly scoped workflow
change. No product file, public MCP schema, default, lock, P0/frozen-v3 artifact
or MPNet threshold was modified. Nothing was merged or activated.
