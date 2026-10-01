# Genuine RU/EN/mixed agent pilot — no gain demonstrated

## Result and decision

Nine new-source questions were executed through a genuine pinned Qwen agent and
the real DocAtlas handler. The language hint and the previous single-host
packing repair produced **no paired gain** on this small pilot. This is a useful
negative result, not an acceptance PASS and not proof that language metadata
never helps. No product activation is recommended from these measurements.

The known HTTPX 5/5 and synthetic 11/11 are NOT the evidence for this conclusion.
The separate multi-host flow regression repair is documented in FLOW_REPORT.md.

## Frozen execution

Code SHA: `767faefef295cfdaa1931f3f9497150f003a7f8b`.
CI run: `36711421082`, three successful execution shards. Each wrote its source,
protocol, task/label, prompt/helper, profile and environment hashes BEFORE its
first agent call. All 11 frozen file hashes, four pinned Git source blobs and
source byte hashes were rechecked after execution. No prompt or label was
changed against these task results.

Sources are pinned Rust borrowing documentation, FastAPI Russian background-task
documentation plus English middleware documentation, and uv synchronization
documentation. There are three subject families, four scopes, three RU, three
EN, and three mixed questions: seven answerable and two unanswerable. The two
negative questions are both mixed. Tasks include EN questions over RU sources,
negative/conditional distinctions, an English minority source, and exact flags.

These sources/tasks were separated from the viewed Typer/HTTPX/M1.5 and failed
v1-pilot files. The same researcher selected sources, questions and facts. They
are not independently human-annotated; FastAPI is related to previously studied
ecosystems. Therefore this is a **fresh, frozen exploratory pilot**, NOT the full
independent acceptance holdout promised in PLAN.md. Nine questions are also not
nine independent subject families. These questions are now viewed development
evidence and must not be reused as a new holdout.

Documents were indexed as project fixtures with pinned but unversioned snapshots.
Dependency version resolution, cold profile delivery, installed stdio integration,
and rendered website include expansion are not validated by this fixture.

## Real model, not stub answers

`Qwen/Qwen2.5-1.5B-Instruct`, revision
`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`; torch `2.8.0+cpu`, transformers
`4.53.3`, FP32 without quantization, eager attention, two CPU threads, seed 0,
no sampling. Maximum new tokens: planning 96, answering 144. No output hit its
length limit. Weights SHA-256:
`dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee`.
All model/tokenizer identity bytes are recorded in each artifact. The model ran
locally on GitHub runners, not as a new dependency of DocAtlas.

There are 18 actual planning generations and 54 answer-condition records.
Of the answers, 24 are actual distinct generations; 30 records reuse a cached
response to a byte-identical message sequence and generation budget. Every
cache reference was checked against the original request, text and token counts.
They are not fabricated replacements, but must NOT be counted as 54 independent
inference calls. Six additional disjoint health generations are recorded outside
the evaluation denominator.

The prior dynamic-INT8 pilot failed intelligibility controls and is retained
separately, not combined with FP32 quality scores. An earlier FP32 preflight
stopped before any task because a correct health answer omitted a citation.
The pre-task amendment separated intelligibility from citation quality; the
frozen task citation rubric remained strict. This is documented in
`pilot_v2.protocol.json`, not hidden as a model improvement on evaluated tasks.

## Conditions and attribution limits

| Condition | Planning | Packet |
|---|---|---|
| A | Real agent, no profile | Baseline |
| B | Same agent, computed warm language hint | Baseline |
| A_packing | Exact saved A query | Prior single-host packing hook |
| B_packing | Exact saved B query | Prior single-host packing hook |
| oracle | No search | Preselected canonical excerpts |
| no_context | No search | Empty evidence |

One lookup of at most 240 characters, at most three sources, 800 DTO tokens and
two sections/source apply consistently. Invalid plans are logged and fall back
to original-only search, without manual repairs, under the frozen intention-to-
treat rule. Original questions and protected literals are retained.

This is NOT full A-E: bounded neighbor assembly and the generic bilingual E
control were not implemented/run. The multi-host flow hook is not this pilot's
intervention. `no_context` is an evidence-only abstention control, not an
unrestricted pretrained-knowledge benchmark. Warm profile delivery overhead
must still be studied for a real caller.

## Review procedure

Only allowed review fields were exported: opaque random ID, question, expected
facts, answerability, final visible evidence, and the exact generated answer.
Condition labels, plans, trace metadata, and task IDs were removed. Identical
review inputs were deduplicated into 24 packets. Every packet is content-hashed.
All semantic judgments were sealed BEFORE joining the private condition key.

Judgment file SHA-256:
`2f6e9a57f954a7ec663d3a8d9921dee3f1a1029d8d4cfbe479faafcbf7536d17`.
Seal time: 2026-09-30 12:10:36 UTC.

The reviewer is the same assistant, not an independent external human or judge
model. Protocol and execution metadata had been seen before masking, but not
condition-labelled answer content. This provides condition masking, NOT fully
independent blind adjudication. `pilot_review.py` validates integrity and joins
complete judgments; it does not pretend to automate semantic correctness.

Scoring follows unchanged PILOT_GRADING.md: a complete packet contains all
facts, not merely overlapping words. Factual correctness rejects contradictions;
grounding and supporting citations are scored separately. Primary answer success
requires factual correctness AND grounding AND valid citations. Answer-language
compliance is reported separately. Missing citations are not waived. Negative
abstention has its own denominator, not counted as a positive retrieved answer.
The grading file's old v1 sample-size description does not define this v2 dataset.

## Reviewed results

| Condition | Complete evidence, /7 positive | Factual answer, /7 | Grounded+cited success, /7 | Correct abstention, /2 negative |
|---|---:|---:|---:|---:|
| A | 2 | 1 | 0 | 1 |
| B | 2 | 1 | 0 | 1 |
| A_packing | 2 | 1 | 0 | 1 |
| B_packing | 2 | 1 | 0 | 1 |
| oracle | 6 | 4 | 1 | 1 |
| no_context | 0 | 0 | 0 | 1 |

A->B, A->A_packing, B->B_packing and A->B_packing each have zero gains and zero
losses in complete evidence, factual answer or primary success. The identical
aggregate results are also identical paired outcomes, not offsetting wins/losses.

All four retrieval conditions have the same language breakdown:

| Query language | Answerable n | Complete evidence | Factual answers | Primary successes | Negative correct/n |
|---|---:|---:|---:|---:|---|
| RU | 3 | 1 | 1 | 0 | N/A, no negative tasks |
| EN | 3 | 1 | 0 | 0 | N/A, no negative tasks |
| mixed | 1 | 0 | 0 | 0 | 1/2 |

Do not infer zero false admission/hallucination rates for RU or EN: no negative
examples were evaluated in those strata. The three clustered families are too
small for a persuasive population effect claim; no independence-based confidence
interval is presented as if these were nine independent trials.

## Why this did not reproduce the optimistic diagnostic result

1. Schema-valid query is not meaning-preserving. A has 7/9 format-valid plans,
   B has 8/9, but B still produces English queries for Russian-dominant sources.
   Some plans choose one side of a question instead of preserving the comparison.
   The uv question about retaining extras becomes a query about NOT saving extra
   packages. The FastAPI either-sync-or-async question becomes an assertion that
   the function must be asynchronous. No manual rewrite corrected these results.
2. The profile is conservative, not a calibrated language census. On the Russian
   FastAPI fixture it counts roughly 10.8% RU and 89.2% unknown prose. In the mixed
   scope it counts roughly 25.3% EN, 6.1% RU and 68.6% unknown. It recommends present
   languages but cannot be described as accurate EN/RU percentages of the library.
3. The weak answerer can misuse sufficient evidence. The uv packet includes both
   flag definitions yet the model says --locked forces an update. A Rust oracle
   explicitly says 'through last use', but the answer says 'until end of block'.
   The factual FastAPI sync/async answer omits supporting citations. The Rust
   unanswerable lifetime question receives an invented numeric duration.
4. Raw Rust Markdown retains mdBook include directives without rendered code.
   Search hits near a rule can therefore lack the full readable witness. This is
   an ingestion/completeness issue, not automatically a language-routing failure.
5. One oracle was not actually sufficient: the uv excerpt omitted the attribution
   of the outdated-lockfile sentence to --locked. It is scored incomplete (6/7
   complete oracle packets), not repaired after seeing answers. A stronger oracle
   precheck and rendering controls are required on a future untouched dataset.

These are documented failure modes, not authorization to retune and reevaluate
these same tasks as a new holdout. In particular the weak oracle results mean the
pilot does not isolate retrieval failure from every answerer limitation.

## Runtime and evidence integrity

36 real handler calls completed with no recorded canonical/budget audit errors;
maximum DTO was 755 tokens; no answer_supported/edit_ready elevation. Source
safety was not independently stress-tested with wrong-project/stale sources in
this pilot, so the audit result is not a general safety proof.

For 42 unique evaluation generations: 9,540 input and 1,645 output tokens;
summed model compute time 456.864 seconds across three workers. Mean planning
latency 6.86 s, answering 13.89 s on that specific two-thread CPU setup. This is
not total wall-clock duration, not a GPU benchmark and not a product SLA; install,
model load, profile acquisition and health controls are outside these sums.

All three artifact SHA-256 values were verified after download:

| Shard | Artifact ID | SHA-256 |
|---|---:|---|
| 0 | 11094108970 | 1b4a18e754212bed1da35a1843a7445b367274c962949f540e7f7aaa5906bc29 |
| 1 | 11093564528 | e3a17be2903dcf9f5c355f7c2d4a44f16606833af407b4e127d9f2a26607d8b4 |
| 2 | 11094497087 | 4a664843565d85b48240e72d7a751b23e4902074755c61f787a4bc7382bc4ba0 |

Artifacts retain real messages, responses, source bytes, freeze files, identity,
traces and failed plans. No credentials or model weights are committed. Actions
retention is seven days; a local evidence bundle also preserves review/seal/key
and scripts for audit.

## Next decision

Keep the profile and both ordering adapters experimental. The narrow flow repair
is useful engineering evidence; it is not evidence for H1/H2/H3 generalization.
Before a further quality experiment, establish a genuinely meaning-preserving
planner and a sufficient canonical oracle on disjoint development controls.
Then freeze a NEW task/source set, compare against the simple bilingual E arm,
use an independently reviewed rubric and adequate answering model, and measure
all costs. No automatic recommendation for MPNet/BGE follows from this failure.
Full independent holdout, neighbor assembly, cold delivery and external blind
review remain outstanding. Do not promote or merge from this pilot.
