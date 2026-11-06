# Renewed quota: targeted post-fix Terra result

2026-11-06. One genuine dev L0/T01-ru session, no retries or additional suite.
Frozen wheel `b8ecfb99faba079faa6c74723be16b0ffee388d20365485f69a7e0ba7d457f8e`;
V1 policy `327fc69db2c97e6d44abbe83118b01fad15a308c071fd5226880c14ee7679a4c`.
This is a **negative minimization experiment**, not V2 validation or acceptance.
Checkout/installed package equality with the wheel was checked before launch.

## Final-answer review

The actual final answer is preserved in `renewed-accounting.json`, with complete
tool trace and per-step usage; raw receipts/config/plan are in `renewed-raw/`.

| Frozen fact | Actual answer excerpt | Fact / citation |
|---|---|---|
| T01.F1, CONTRIBUTING.md:61 | `feat/<topic>` … `fix/<description>` | PASS / PASS |
| T01.F2, CONTRIBUTING.md:62 | «До открытия PR запустите полный набор тестов» | PASS / PASS |
| T01.F3, CONTRIBUTING.md:63 | «Для новых коннекторов или fetcher-компонентов добавьте тесты там, где это практически возможно» | PASS / PASS |

All three claims cite CONTRIBUTING.md:59–63, evidence
`ev-dc2112ec2f32298ae05568ea`, actually delivered. Independent source text matches.
Additional claims about test commands, onboarding documents, Docs MCP inventory,
and advisory documentation review are supported by their retrieved citations.
The offline-suite qualification is appropriately distinguished from the full suite.
Six citation paths/ranges/evidence IDs verified. No invented requirement found.

**Question-preservation FAIL:** original user prompt/plan is unchanged, but the
agent's MCP `question` adds literal surrounding double quotes. `search_question`
equals the frozen complete translation. We do not normalize this discrepancy or
claim an unchanged-question server experiment. Provider availability is confirmed.

## All-step comparison

| Measure | Renewed candidate | Existing file baseline |
|---|---:|---:|
| Required facts | 3/3 | 3/3 |
| Input | 58475 | 3967 |
| Cache read | 2944 | 1280 |
| Input + cache read | **61419** | **5247** |
| Output | 660 | 402 |
| Reasoning / cache write | 0 / 0 | 0 / 0 |
| Model steps | 4 | 3 |
| Wall seconds | 111.57 | 13.77 |

Candidate input+cache is **11.706×** baseline. Both ledgers reconcile all recorded
step_finish events with persisted session totals. No monetary-cost claim.
Three candidate top-level calls: resource discovery, docs_status and context;
two nested calls are wrappers, not two additional product requests. One context
request, no continuation or source-focus recovery. No provider errors/censoring.

Reuse evidence: same Terra model/low variant, same original dev case, no step
ceiling, same frozen corpus path; historical baseline artifact hashes unchanged.
All 63 CONTRIBUTING and 5 testing lines from historical reads match current files;
frozen questions/oracle/witness hashes match. This justifies a case-local
observational comparison. Historical full-corpus/store hash manifest is absent:
do not claim retrospective complete snapshot equality. Prompts/tools differ by
arm deliberately; this is not an isolated causal adapter experiment.

## Concrete diagnosis and next gate

The selector admits **152/157 units (96.8%) directly**, before closure;
closure adds five, delivering **157/157 across 19 documents** (1398 model pairs).
Thus this run cannot attribute excessive cost solely to structural expansion or
the adapter: relevance admission is already almost keep-all. Both unresolved
dependencies remain explicit (`target_not_in_checked_scope`, missing anchor),
and context quality remains unverified. Independent offline audit verified exact
source text/line spans, canonical material hashes and declared catalog scope for
all 157 rows (144 project, 13 module). This is catalog consistency, not a fresh
authorization or replay test.

No full L2/V2 suite is justified: V1 broad L2 already exceeds emergency50k and V2
independent no-answer gate already fails. A next general mechanism must separate
query-relevant own-body evidence from heading/context similarity **before** full
structural closure, and pass fresh independently labeled positive/no-answer cases
with frozen calibration before another Terra suite. Existing V2 min-score gate
does not meet that requirement. No threshold, closure, rubric or source was
changed to force this case to pass. Exact-question forwarding is a separate
client contract defect; stripping quotes server-side would obscure it.

## Reproduce offline checks

```sh
/tmp/opencode/step10-final-py313/bin/python eval/blind_project_context/step10-agent-evaluation/account_sessions.py --root /tmp/opencode/terra-step10-renewed --output eval/blind_project_context/step10-agent-evaluation/renewed-accounting.json
/tmp/opencode/step10-final-py313/bin/python eval/blind_project_context/step10-agent-evaluation/audit_renewed.py
```

Audit output: `renewed-audit.json`; preserved artifacts: `renewed-artifacts.json`.
The first offline audit incorrectly assumed every row must be project-scoped;
inspection found 13 module rows declared in the frozen catalog, so the evaluator
now checks exact catalog scope per source. This changed no product or rubric.
Missing portable performance receipts/tables restored under `performance/` from
the three historical profile directories. Their raw binary profiles remain at
the external paths in `performance/README.md`; copied diagnostics retain their
original censored scope and are not new runtime measurements.
