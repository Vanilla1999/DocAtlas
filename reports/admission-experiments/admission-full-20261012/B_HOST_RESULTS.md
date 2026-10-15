# B — actual host readiness and B0 answers

> Follow-up checkpoint: `B_FINAL_SUMMARY.md` records the coordinator's12 later calls, exact-citation FAIL for both Q16 generations, and the explicitly authorized **18 total later-call ceiling** (six remaining). The initial B0/readiness receipts below are historical and unchanged. Budget-only runner patch has a new hash; no calls were made by B for that patch.

## Outcome

**Existing configured alias works; no substitution.** One readiness request and two B0 generation requests completed through OpenCode V2's stateless text endpoint. Q46/Q16 both honestly abstain on the actual empty current-head public packets. A better host prompt does not recover facts withheld by server admission. These observations do not establish that the host would answer correctly with B1 context.

Requested model: `openai/gpt-5.6-luna#medium`. `tools.opencode.models(provider=openai, query=gpt-5.6-luna, all=true)` discovered this exact active alias and medium variant; no physical weights/revision or price was exposed. Current assistant identity was not substituted. CLI/service version `2.0.27`; existing local service reported `http://127.0.0.1:49374`.

| Case | Public sources | Actual response | Citations | CLI/API wall time |
|---|---:|---|---:|---:|
| readiness | no corpus | `{"ready":true}` | — | 1.392334s |
| B0 Q46 | 0 | `status=insufficient`, cannot determine PASS criteria from the supplied packet | 0 | 1.862995s |
| B0 Q16 | 0 | `status=insufficient`, comparison information not supplied | 0 | 1.918373s |

Raw complete answers and messages: `B_B0_Q46/`, `B_B0_Q16/`. Each directory contains `request.json`, `messages.json`, `command.json`, `provenance.json`, `response.json`, `answer.raw.txt`, `answer.json`, `receipt.json`, `validation.json`. Readiness receipt: `B_host_readiness/`. Concise structured summary: `B_HOST_RESULTS.json`.

The existing product packets came from CI38232527945 at HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`, artifact hash `8395cc9c62f2f9d1fc3d4a1ca60786b996b6f990c277a8272d28e442118dd285`. There was no fresh product call or product import. The runner verifies the artifact and head receipt, takes each unchanged question and confirms absent public sources. **Only question + sources=[]** go to generation: no required facts, private diagnostics, missing-facts oracle, source-policy audit or corpus text. Common `HOST_PROMPT_RU.txt` hash is verified before rendering. S1/R1 files remain unchanged and hash-verified; their inference is **NOT RUN**.

Both outputs are valid requested JSON and contain no invented citations. Source-supported complete answers: **0/2**; required facts remain undelivered. A source-only refusal is appropriate for these packets, but does not count as solving the original user questions. G independently reviews final quality; B does not award itself experimental PASS.

## Transport limits — do not conceal

Endpoint: `opencode api post /api/experimental/generate --data <request JSON>`, through existing authenticated service. It is stateless text generation, not a child agent: no session conversation/history, agent tool loop, or tool schema is requested. Wrapper serializes the frozen logical system/user messages into one prompt; it is **ADAPTED**, not a claim of native role-identical author prompt reproduction. Exact submitted prompt bytes and logical messages are recorded separately.

The response contract exposes only `data.text`. **Input/output/reasoning tokens, billing, actual backend model revision, provider-wire messages, output token cap, temperature/seed and HTTP retry count are NOT EXPOSED.** Receipts contain null/status fields rather than zero/fabricated usage. Latency is measured runner wall time, not isolated GPU inference. One runner attempt per request, no format repair/retry/fallback; transport-level retries cannot be certified zero from this endpoint. If coordinator requires verified HTTP call counts, token caps and billed usage, this transport is insufficient for those metrics and must not be presented as meeting that measurement contract.

OpenCode V2 skill and official CLI/API pages were consulted. The repo's earlier `--dir/--variant` invocation shape is not this installed CLI's shape; no speculative legacy invocation was used. Public `dev` endpoint source was inspected for text-only generation behavior, but is **not asserted identical to installed2.0.27**. Context7 lookup was attempted but quota was exhausted; official V2 docs/OpenAPI supplied the endpoint contract. No credentials, auth files, private global config or service logs were read or printed.

Execution counts: **3 endpoint invocations total = 1 readiness + 2 generation; S1=0, R1=0, extra product=0.** Provider HTTP count and tokens are unknown. Total measured wall5.173702s, generation-only3.781368s. Do not repeat either B0 command: output directories are exclusive attempt receipts and the runner refuses reuse.

## Coordinator runnable commands

Already executed; **do not rerun**:

```sh
python3 /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B_host_runner.py readiness
python3 /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B_host_runner.py b0
```

Later calls are prepared but have not been executed. Coordinator first produces a **normalized actual public packet**, after checking source-policy/provenance, in a separate evidence file:

```json
{"question":"unchanged original question","sources":[{"source_id":"stable public evidence/candidate ID","text":"complete unchanged source text"}]}
```

Only these exact keys are accepted; no oracle/diag. For R1, `sources` must be the **full observed policy-valid candidate pool**, not oracle-chosen supporting spans or only final projected snippets. It is supplied by A/coordinator; the runner does not manufacture a candidate pool or certify source admissibility. No word/token crop or top-k cap is applied. Package size is recorded in provenance. Exact text/spans/hash/scope/policy proofs stay in the coordinator's local sidecar. For S1/generation, use the actual selected final public packet, not the longer acquired pool.

On explicit coordinator command only, with a distinct stable run ID per invocation:

```sh
python3 /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B_host_runner.py later --role generation --input /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B1_Q46_public_model_input.json --run-id B1_Q46_generation --coordinator-command 'coordinator-approved B1 Q46 generation'
python3 /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B_host_runner.py later --role sufficiency --input /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B1_Q46_public_model_input.json --run-id B1_Q46_S1 --coordinator-command 'coordinator-approved B1 Q46 S1'
python3 /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B_host_runner.py later --role ranking --input /tmp/opencode/docatlas-review-evidence/admission-full-20261012/B1_Q46_policy_valid_pool_model_input.json --run-id Q46_R1 --coordinator-command 'coordinator-approved Q46 full-pool R1'
```

The sample input files above **do not yet exist**; commands must not be run until actual packets and explicit approval exist. `--coordinator-command` records authorization provenance, it does not grant permission. Up to14 additional calls total, each counted by persistent `B_later_*/receipt.json` (failed attempts count); **coordinator must run serially** so budget checks do not race. Each unique output directory can be created only once. R1 output strict permutation/partition validation, S1 field validation, and host output schema validation are implemented; no model-output repair. These are adapter validations, not unit tests or independent quality verdicts. No S1 judgment is a delivery veto.

`B_host_runner.py` uses Python stdlib and the existing CLI only, no installs or shared C runtime. Runner SHA-256 `1dc25531f1bd5cb440ad56a3fc7f939a08d66d0275fa65536dfd60d0ca8423ee`. B edited no repository files. Final repo status showed three concurrent A-owned domain edits; they were not altered, reverted, or attributed to B. B0 packets remain explicitly tied to the recorded clean CI HEAD, not to that uncommitted worktree.

Next: coordinator/G review these two raw refusals, provide actual B1 public sources/full policy-valid pools and explicitly approve desired calls within14. Physical model revision/token usage/retry observability remain measurement blockers, not inference availability blockers.
