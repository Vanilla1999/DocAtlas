# Host-only learned candidate ordering

> **Status: retained as an optional experiment — verification required.**
> Owner decision (2026-10-13): keep the pinned MiniLM reranker, but do not enable
> it by default or claim it solves context sufficiency. The P03/E01 pilot failed
> both unchanged full-witness criteria; full V40 comparison was not executed.
> Remaining checks: `v2plan/MINILM_VERIFICATION_TODO_RU.md`.

`experimental_candidate_selector` is an opt-in experiment context manager, not a
public MCP request field or default model dependency. Inside a live source-bound
native documentation read, its callback receives `question` and an immutable
tuple of complete `passages`. It must return a complete permutation of the
checked pool's integer indices. Missing, duplicate, added, boolean or out-of-range
indices fail explicitly. Model errors propagate; no silent baseline fallback.

The callback cannot modify source objects, rewrite evidence, discard candidates,
grant authority, change scope/version/consent or relax the final delivery budget.
Unchanged downstream projection and source rechecks still decide delivery.
Without the context manager, ordering remains the original native order.

The optional experiment runner `eval/heuristic_removal/learned_order.py` uses a
pinned local MS MARCO MiniLM ONNX model. It ranks full question/passage pairs by
raw logit, stable original-index ties, without top-k, thresholds, truncation or
new lexical rules. Complete inputs beyond model positions fail explicitly.
Learned order is not a sufficiency score or permission to answer. No model is
installed or loaded by ordinary queries. No quality improvement is asserted here.

The paired integration experiment retains the full public DTO budget and checks
independent frozen witness delivery, source validity, equal admitted pools and
read-only state. See the frozen protocol in
`reports/docatlas-grounded-20261013/learned-order/PROTOCOL_RU.md`.
