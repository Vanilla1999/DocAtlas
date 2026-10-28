# Experimental independent autorater and bounded recovery — PR #232

This extension is OFF unless an explicitly configured managed host constructs
`SufficientContextSession`, or invokes `python -m docmancer.docs.interfaces.sufficient_context_cli`.
It is NOT automatically activated by the ordinary OpenCode MCP installation.
The selector stays opt-in via `DOCATLAS_LLM_EVIDENCE=select`.

## Actual boundaries

1. Existing public MCP retrieval, source admission and optional Qwen selection.
2. `FinalContextAutorater` sees ONLY the final model-visible context and original
   question, not omitted pool rows, selection verdicts, final answers or gold.
   A different provisioned weight fingerprint is required. The experiment uses
   Microsoft Phi-4-mini-instruct (bartowski Q4_K_M) versus Qwen3-4B Q4_K_M.
   Different families do not imply independent errors or proven correctness.
3. The host mechanically validates source IDs and exact quotes, derives the
   overall status from supported/missing/uncertain fields and binds the verdict
   to the exact context hash. This validates structure, NOT semantic relevance.
4. For a concrete gap, the host issues at most one extra public
   `get_docs_context` by default, with the ORIGINAL question and immutable
   project/library/module/scope/version bindings; only `lookup_queries` changes.
   No preparation, writes, consent bypass, remote corpus or automatic web search.
5. Reassess the actual final accumulated context. Stop on sufficient judgment,
   unchanged evidence, repeated search, unavailable checker, bounds or deadline.
6. A managed answer call uses full-answer guidance for sufficient and
   supported-only guidance with explicit gaps for partial. Unknown/insufficient
   returns a typed abstention without a paid call. Neither branch grants source,
   edit or execution authority. Actual answering-model compliance is an
   empirical property; a prompt is not a proof against hallucination.

The original Qwen `select-audit` experiment remains unchanged for historical
comparison. This is not a second pass over the whole pool pretending to grade
an already selected subset. Source bytes are never generated or rewritten.

## Evidence and budgets

Sources already retained by the managed session are not discarded during
recovery. The existing complete-input budget also prices added guidance. There
is no new 3,000-token limit. Operational failure is distinct from missing facts.
The loop has a bounded number of searches/checks and a deadline before NEW calls;
in-flight HTTP calls still have their own timeout. Invalidate on source/access
changes; a stale verdict/answer cannot survive the session epoch or context hash.

Paid requests require an explicit API key AND model; there is no default model,
remote fallback, tool execution or retry. Raw provider usage includes input,
output and available cached/reasoning detail, including unsuccessful generations.
Missing usage is unknown, never zero. No local token counts are sold as billed
savings. Model latency and serving-process VmHWM are recorded separately.

## Research scope

- Sufficient Context, ICLR 2025, https://arxiv.org/abs/2411.06037:
  question-context sufficiency, distinct from final-answer correctness. Its
  autorater/calibration and confidence-based selective generation are NOT
  reproduced. This prompted Phi model must pass its own measurement.
- Corrective Retrieval Augmented Generation, https://arxiv.org/abs/2401.15884:
  evaluation-driven corrective retrieval. Its trained T5 evaluator and web
  expansion are NOT reproduced; our recovery stays within authorized sources.
- Phi upstream: https://huggingface.co/microsoft/Phi-4-mini-instruct .
  Quantization: https://huggingface.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF .
- Paid API schema/accounting: https://developers.openai.com/api/docs/guides/structured-outputs .

No independent training, universal minimality, guaranteed absence or guaranteed
quality follows from naming these papers.

## Preregistered evaluation

Twelve frozen, separately scored controlled-context scenarios pass through a
real installed MCP before the judge: sufficient/partial/insufficient/conflict,
missing exception, missing prerequisites, Russian and injected document prose.
The separate set is same-author synthetic, NOT human-independent calibration.
A false-sufficient label is a primary failure, not hidden by aggregate coverage.
The four unchanged L10-03/04/07/08 episodes compare main, Qwen select, main with
the recovery loop, and Qwen with the recovery loop. Source coverage uses frozen
original alternatives. A request that errors is a failure, not a token saving.
End-to-end answer correctness is NOT inferred from the judge's verdict or a
quote-coverage score.

`eval/sufficient_context/run.py` runs in an installed wheel with actual SQLite,
public preparation/stdio, checksum-pinned local models and the previously built
pinned llama.cpp runtime. It reports actual paid responses only when the existing
repository secret OPENAI_API_KEY and variable DOCATLAS_STRONG_MODEL are present;
otherwise paid comparison is explicitly BLOCKED_NOT_CONFIGURED. No synthetic
answer or substitute local usage fills that gap. The workflow completing means
measurement succeeded, not semantic acceptance or approval for default use.

Before promotion: separately reviewed held-out cases, controlled paid-model A/B,
answer grading, false-abstention/false-sufficiency reporting, real target-device
latency and memory, and native host integration if ordinary OpenCode is required.
