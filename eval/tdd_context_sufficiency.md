# T05: separate assessed-claim acceptance

`eval/tdd_context_sufficiency.py` is a report-only sidecar. No runtime code imports it. It does not replace `eval/evidence_quality_v2/semantic.py`, alter frozen thresholds, infer semantic support from keywords, or measure a host model's final answer.

The input is an existing `assess_context` result and an independent inventory of required claim IDs from the pinned case. Three external checks must be supplied explicitly: transport, source/span/hash integrity, and packet budget. Use `None` for a check that has not been measured. Do not copy a retrieval coverage score or `status=ok` into these checks.

```python
from eval.evidence_quality_v2.semantic import assess_context
from eval.tdd_context_sufficiency import summarize_assessment

assessment = assess_context(case, visible_payload, source_registry)
summary = summarize_assessment(
    assessment,
    required_ids=tuple(claim['id'] for claim in case['required_claims']),
    transport_ok=verified_transport_result,
    citation_integrity=verified_source_span_hash_result,
    budget_ok=verified_complete_packet_budget_result,
)
```

The three `verified_*` values are inputs from independent checks, not functions implemented here. Tests use explicit synthetic checks and make no claim that a synthetic snippet has passed the production hash validator.

## Policy

- Missing required facts, contradictions, rejected sources, or a failed independent check produce `FAIL`.
- Pending review is retained even when every recognized required claim is supported. Without a definite failure it produces `REVIEW_REQUIRED`, not a claim that the answer is false.
- Unknown independent checks produce `NOT_EVALUATED`, unless a definite failure or pending review already takes precedence. The unmeasured check names are always retained.
- `PASS` requires all required claims, no pending review or contradiction, no rejected sources, and all three independent checks explicitly true.
- Optional facts do not change the required denominator. Optional contradictions and pending review are still surfaced.
- A malformed/missing inventory raises `ValueError`; an empty inventory is not perfect coverage.
- `final_answer_quality` is always `NOT_MEASURED`. A sidecar verdict cannot grant answer support or edit authority.

Retain the raw assessment beside this summary. Do not rewrite historical scores or reinterpret `needs_review` as a product failure. This policy is a new explicit acceptance view, not an alleged bug fix in the conservative semantic evaluator.

## Claim boundary and remaining work

This implements the T05 reporting layer only. The 30-question regression corpus, eight historical first-loss fixtures, expectation revision records, contamination checks, exact-commit replay, and selection tracing remain separate work. It is not a completed T05–T12 acceptance run or evidence of improved answers.

Existing research motivating the separation was reviewed in the TDD plan: Sufficient Context (arXiv:2411.06037) distinguishes context sufficiency from use by a model; ALCE (EMNLP 2023, 2023.emnlp-main.398) separates correctness and citation quality. Neither proves the quality of this implementation. Behavioral tests, including integration with the unchanged semantic evaluator, provide the evidence here.
