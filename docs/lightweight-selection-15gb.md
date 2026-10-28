# Main-based evidence selection under a hard 1.5 GB budget

## Contract and baseline

Start from main `439815771b96edc77a12f42f90f1fecb35f5e5d7`, not PRs #230–232.
The main path already uses provisioned MiniLM plus `facet-guarded-lexical-v2`;
fixed-five is an explicit rollback, not the current default. LiteLLM is a provider
SDK, not MiniLM and not a model. No provider dependency is added here.

No changed default, new 3,000-token cap, source rewriting, remote inference,
automatic downloads during requests, new authority or corpus-wide absence claim.
The existing full-packet budget and source validation remain. Explicit compression
OFF remains OFF. Heavy Qwen3-4B, Phi and the recovery/autorater host are not imported.

The runtime experiment enforces **1,500,000,000 bytes** on ONE Linux cgroup that
contains the evaluator, Python/MCP, SQLite, MiniLM when loaded, and at most one
small model server. Swap is disabled; two CPU cores; runtime network is disabled
except the container's loopback. We count `memory.peak` and OOM events for the whole
group, not weight size or separately sampled per-process maxima. Setup/downloads
and image building are outside this request-memory contract. A Python flag does
not enforce memory on arbitrary users' machines; the host must enforce the budget.

## Preregistered alternatives

1. `off`: unchanged main, plus separate fixed-five control.
2. `minilm-window`: retain main selection; replace the 128-query-token rejection
   with exhaustive nonoverlapping query windows and native passage windows,
   aggregating MaxP-style. No query token is silently dropped. Resource caps and
   section-selection heuristics are inherited. This is an engineering ablation,
   not a trained semantic obligation detector or a reproduction of a paper.
3. `qwen-rerank`: Qwen3-Reranker-0.6B, a task-trained relevance model, using its
   native yes/no classifier (probability >= 0.5, without tuning on evaluation).
   Keep complete positive sections, not an arbitrary top-five. An overlong section
   is retained unscored. Relevance probability is NOT sufficiency probability.
4. `qwen-select`: official Qwen3-0.6B Q8_0 in nonthinking mode selects IDs of whole
   source sections. Authority and instruction-trust metadata are included. Full
   section batches share the original question, up to four batches and 2,048 model
   context tokens; all batches are planned before generation. This small context
   is a resource constraint, not a content target or a global corpus cutoff.

Both Qwen paths have a ten-second client-side selection deadline. If planning,
all batches, schema validation or encoding cannot finish, discard the alternative
and use unchanged main. Closing a timed-out HTTP request is not a proof of server
cancellation; server logs and subsequent latency must be inspected. Fallback can
still encounter main's query/resource errors. It must not be counted as successful
new model selection. There is no extra checker, repeated search or forced unknown.
Batching can lose cross-document semantic interactions; this is a measured risk.

## Research basis and what is NOT claimed

- Qwen3 Embedding / Reranker technical report: https://arxiv.org/abs/2506.05176
  and official model card https://huggingface.co/Qwen/Qwen3-Reranker-0.6B .
  This arm really uses trained reranker weights, not an ordinary chat model with
  the research name attached. GGUF quantization and our binary cutoff are separate
  deployment choices; published benchmark results do not validate these choices.
- RECOMP: https://arxiv.org/abs/2310.04408 . Motivates extractive selection before
  an answering model. Its trained compressors are not reproduced by our chat prompt.
- LLMLingua-2: https://arxiv.org/abs/2403.12968 . A relevant learned token-compression
  alternative, not implemented here: token deletion needs a new source-span
  contract and must not silently remove negations/conditions from source evidence.
- Sufficient Context: https://arxiv.org/abs/2411.06037 . Separating evidence
  adequacy from answer correctness is useful; no tested lightweight autorater is
  claimed. Earlier distinct-Phi failures are not paper failures or a reason to add
  another heavy verifier blindly.

The compact structured wire format is main's reversible encoding and is used
uniformly. We do not present its existing savings as a new selector improvement.

## Frozen evaluation

Reuse unchanged V40 (40 questions) and the disclosed known L10 (10 questions from
PR #232; only fixtures copied, no product code). Add eight authored fictional
questions with seventeen positive requirements, Russian/English, versions,
conditions across files, adequate alternative sources and unsupported requests.
New fixtures were written by the implementation author: NOT blind/human-independent
acceptance. Freeze bytes before inference, parse expected witnesses after delivery,
never adjust gold or thresholds to produce PASS.

Same installed wheel, real public preparation, stdio MCP and SQLite. No mocked
retrieval, selection, source validator or inference. Compare independent original
quotes/spans delivered to the client, new losses versus main, complete documented
cases, all reply text tokens including errors, and latency. Paired token savings
must use the same successful questions; a short error is not a saving. Unknown
correctness and final answers are not inferred from missing gold or source recall.

The cgroup experiment also checks unchanged source/SQLite state, unavailable-model
fallback through public MCP, and explicit compression OFF with a configured model.
All raw replies, errors, traces, hashes and memory data are retained. A green
measurement job is NOT semantic acceptance. If a process is killed for memory,
report OOM, not missing results as zero cost. Exact selected fields must match the
same-question authorized pool, including original text/lines/scope/version/trust.

The official chat GGUF is pinned by revision, exact byte size and SHA-256. The
third-party RANK conversion is resolved to a commit/LFS digest before inference;
its manifest is saved and accepted as a reproduction input. llama.cpp is pinned
to `8642541b255bfb5dc39cd351a178be09013a55d6`. No downloaded Python model code runs.

## Paid-model boundary

Primary product goals: adequate answers, lower PAID-model usage, acceptable total
latency, and memory within budget. Local token counts are not a bill. This study
measures source retention and complete MCP text as a proxy only. It does not run
stock OpenCode or a paid answerer. Provider access status is explicit; usage stays
null. No zero-usage saving, paid bill reduction or correct-unknown acceptance is
claimed. Provider-backed whole-dialogue A/B still requires explicit access and the
same paid model, prompt, questions and error accounting.

## Reproduction

Workflow: `.github/workflows/lightweight-evidence.yml`. Selectors are enabled only
by the host `DOCATLAS_LIGHT_SELECTION` setting while normal compression is enabled.
Local runtime: use the supplied Dockerfile and launch script under the exact
`--memory=1500000000 --memory-swap=1500000000 --cpus=2` constraints. Reproduce GGUF
resolution with its saved manifest, not a subsequently moving repository branch.
