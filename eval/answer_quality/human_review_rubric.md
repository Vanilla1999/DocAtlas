# Task 43 bounded human-review rubric

This rubric covers qualities that the executable gate must not reduce to a
substring score. It supplements the deterministic gate and cannot override a
failed citation, provenance, correctness, or token check.

## Frozen sample

Review exactly the six contracts in `human_review_selection_v1.json`. Do not
replace a difficult case after seeing its output. Review the canonical
model-visible projection and the sanitized evidence manifest; do not inspect
hidden tests or tune the protocol from the observed result.

## Ratings

Use `PASS`, `FAIL`, or `INCONCLUSIVE` for every dimension and add one concise
reason. A case passes human review only when every dimension is `PASS`.

1. **Directness** — the result answers the question or states what is missing
   without generic filler.
2. **Ambiguity** — identifiers, versions, targets, and ownership boundaries are
   unambiguous enough for the requested use.
3. **Citation usefulness** — evidence references are adjacent or easy to map to
   the claim they support.
4. **Snippet completeness** — code/signature/config snippets include the
   minimum symbols and context needed to use them safely.
5. **Omission disclosure** — material missing evidence or uncertainty is stated
   explicitly and does not authorize an unsupported edit.

## Reviewer record

The checked-in review artifact must record reviewer identity, UTC timestamp,
protocol SHA-256, result digest, the six per-case ratings, and an overall
verdict. Missing reviewer identity or any `INCONCLUSIVE` dimension keeps the
human-review gate `INCONCLUSIVE`.
