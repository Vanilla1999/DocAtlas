# Independent review of final context boundaries

Reviewed base: `47a636e73268f1c39495b83cda82c7a0a0c9674e`.
Reviewer: separate boundary-review agent, read-only for product and tests.
No product call, pytest run, retrieval, indexing, or model call was performed by
this reviewer. The coordinator owns runtime execution.

## New finding: budget compaction rewrites an existing operational refusal

Severity: P2, public contract/diagnostic regression. This finding does **not**
claim that a forbidden source is returned or that edits become authorized.

`context_tools.handle_context_tool` calls `_explicit_delivery_block` before
projection. That producer deliberately returns `delivery_decision.deliverable`
equal to false, the operational reason, and `confirmation_reason` when present.
The experimental cap is then applied to this already empty refusal.

When the cap is exceeded, `experimental_context_finalization._rebuild` uses a
fresh generic empty selection and copies only six optional fields from the old
payload. It drops `delivery_decision` and `confirmation_reason`. It also replaces
the existing `context_quality.reasons` with `budget_limited`, even when source
delivery was already denied independently of the budget.

Relevant base code:

- `docmancer/docs/interfaces/mcp/context_tools.py`, early blocked return.
- `docmancer/docs/application/model_visible_projection.py`,
  `_explicit_delivery_block`.
- `docmancer/docs/application/experimental_context_finalization.py`, `_rebuild`
  empty-result branch and `enforce_experimental_context_budget`.

The existing archived public stale response in
`../implementation-20261012/run-03-packets/context-e19bf6322a3849ecba140949aa0285f4.json`
has a real denial, `requires_confirmation=true`,
`confirmation_reason=project_docs_preflight`, and
`context_quality.reasons=[source_unavailable]`. Its complete ordinary JSON is
618 UTF-8 bytes, or 155 under the rounded UTF-8/4 measure. The old cap of 900
never exercises the faulty branch for this packet.

A static JSON reconstruction of the base empty-rebuild branch is 517 bytes,
or 130 under the same measure; this is **not** a product runtime result. It shows
that a fixed cap of 150 provides a feasible public reproduction: reuse the
existing real prepare/update/stale-read workflow and assert that the typed
denial and the reason for confirmation survive compaction. No question rewrite,
new source fact, mocked retriever, or model call is required. The runtime must
also check the independent token measure, exact returned DTO, and unchanged
project/store state.

Recommended repair: compact an already empty operational refusal as that
refusal. Remove duplicate explanatory fields before dropping anything that
describes delivery, confirmation, or the original reason for source
unavailability. If the remaining required envelope cannot fit, report a host
configuration error instead of weakening those fields.

## Checks that did not establish another defect

- The previously reported coverage resurrection has already been corrected in
  the reviewed base. `_rebuild` requalifies visible rows, caps credit by the
  previous public `covered_query_ids`, rejects admission-only credit, and clears
  assignment proof. This review found no second independent resurrection in
  that branch. This is source review, not a new integration pass.
- Source URI registration does not normally increase packet size after cap
  selection. Locators are attached before the terminal budget; the final binder
  registers existing locators or removes unavailable ones. A speculative
  "new URI pushes a fitted packet over cap" finding is therefore not supported.
- Native fallback candidates come from the already admitted, captured same-call
  pool and are independently validated. `_native_alternatives` checks textual
  containment rather than exact coordinate containment. Repeated text could
  make that relation ambiguous, but this review has not established a real
  public wrong-source result or a violated authorization boundary from it. It
  is not counted as a reproduced defect or a reason to add question-specific
  filtering.

## Tailoring assessment within this review's scope

The confirmed defect depends on the operational state and serialized packet
budget, not on the subject, numbers, or wording of the user's question. Its
repair should preserve the same rule for every already empty refusal. This is
not evidence that broad source-valid admission solves semantic relevance or
that the previous small fixture corpus proves generalization. Those claims
require separate evidence.

Runtime reproduction and any final fix are to be recorded by the coordinator
with their own exact code version and outputs; this note is the pre-fix review.

## Coordinator's reproduced failure and exact fix review

The reviewer subsequently inspected both saved `run-01-packets` public DTOs,
`run-01.log`, `run-01.xml`, the execution ledger, and the actual product diff
against the base. The coordinator executed one real preparation and two public
context calls; the reviewer still performed no product/test runtime.

The wide packet
`run-01-packets/context-139c136fa3e44b349f74c78db902a2d0.json`
contains the original typed denial. At cap 150, the returned packet
`run-01-packets/context-e446a35db9114d349d1f9e7e0a666258.json`
really loses both `confirmation_reason` and `delivery_decision`, and changes
the quality reason from `source_unavailable` to `budget_limited`. Both responses
have zero sources and false context/answer/edit flags. Their saved whole-JSON
UTF-8/4 costs are 155 and 130. Pytest fails at the first field mismatch,
`confirmation_reason`; the additional two losses are independently visible in
the captured response, not inferred from the abbreviated assertion. The failure
therefore confirms the proposed defect rather than a fixture/import problem.

The exact repair reviewed is confined to `_rebuild`:

1. The new early branch applies only if the incoming public payload already had
   no sources and the requested output rows are also empty.
2. It copies that payload, clears `read_next`, drops the optional
   `recommended_next_action`, and removes `missing` only when it is exactly the
   duplicate singleton `[reason_code]`.
3. It refreshes the estimate and returns no source bindings. All typed denial,
   confirmation, operational, and original quality fields survive unchanged.
4. The later incomplete whitelist is deleted because this branch now owns the
   already-empty case. An originally nonempty packet whose sources are omitted
   still uses the existing generic empty-selection budget explanation.

The existing terminal cap and public validator remain the final checks. The
repair adds no retrieval, no model, no new source grant, no question-dependent
condition, and no exemption from the cap. This exact product diff is approved
by the boundary reviewer, subject to the coordinator's recorded integration
result. The regression question and documents remain the previous optics/stale
fixture; only the operational condition under test differs from the old cap-900
stale call. The new regression assertions did not change after the reproduced
failure.

## Post-fix result independently checked

The reviewer inspected the coordinator's `run-02.log`, execution ledger, and
both repaired-refusal DTOs. The run reports five passing integration nodes in
4.34 seconds; this subsection independently audits the refusal node only.

| Actual public response | Complete JSON UTF-8 bytes | Rounded UTF-8/4 | Delivery/confirmation/quality |
| --- | ---: | ---: | --- |
| Wide-cap control | 618 | 155 | Original typed refusal |
| Before fix, cap 150 | 517 | 130 | Loses typed delivery and confirmation reason; wrong quality cause |
| After fix, cap 150 | 576 | 144 | All original typed refusal fields retained |

The repaired response is
`run-02-packets/context-7e5a0b19c23a4d90babe24ef0dee029e.json`;
the paired wide-cap response is
`run-02-packets/context-18f53486f35b4f30ab765150249e390b.json`.
Independent JSON serialization of these saved payloads found only two differing
keys: `missing` (the exact duplicate was removed) and `estimated_tokens` (updated
for the smaller packet). Delivery denial, confirmation, reason, quality,
status, and all false context/answer/edit flags are identical. Sources and
`read_next` remain empty. The completed public integration additionally asserts
unchanged project files and logical database state.

The whole-wire byte counts above were independently recomputed from saved data
without importing or calling the product. They are not a separate measurement
of the offline tokenizer or the host's full prompt. The product's terminal
combined cap check ran in the real public call; the public regression succeeds
at the frozen cap of 150.

SHA-256 checked against the run ledger and current files:

- Refusal regression, unchanged from the failing run:
  `8bba9d86ff4a976775d3a78ce5e6e5752f9ddaaa1eef495ed23d04255ac597df`.
- Repaired `experimental_context_finalization.py`:
  `26624db4ba133edcbdaba6d2a3b30472740d1e5bf6637a7def84a45f0fe0e41f`.

Boundary-review disposition: the confirmed regression is fixed and the same
public test changes from FAIL to PASS without a post-failure oracle edit. No
additional runtime or speculative product change is requested by this review.
