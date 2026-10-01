# Frozen pilot grading rubric (before inspecting generated answers)

The 12 tasks and facts were committed at 2a927824bcbb9c6e4e124bd9916a37c025e0f866,
with immutable public source blob IDs. They were not used to tune the previous
one-host packing intervention. This is a four-family pilot, not 12 independent
families and not the full proposed 36-case acceptance benchmark. The source/task
author and this reviewer are the same assistant: do not call this independent
human annotation or an external expert judgment.

## Blinding

Export final question, expected facts, answerability, actual visible evidence and
model answer under random opaque IDs, omitting arm, query plan, profile, model
cost, retrieval trace and filename. Preserve the key separately. Review every
unique (question,evidence,answer) record once. Byte-identical model generations
may be reused across conditions; preserve links, not additional fictitious calls.
Write and hash all judgments before joining the treatment key. The reviewer is
blind to condition labels, not to task authorship or whether evidence is empty.

## Scores

- `packet_complete`: for answerable tasks, all frozen facts (conditions/negations
  included) are visible in the actual evidence. Keyword co-occurrence is not
  enough. Unanswerable tasks have null here, not an automatic retrieval success.
- `factually_correct`: answerable tasks require every frozen fact and no factual
  contradiction; abstaining is not a correct answer. Unanswerable tasks require
  explicit insufficiency/non-documentation and no invented numerical limit.
- `grounded`: every substantive assertion is supported by the supplied evidence;
  appropriate abstention is grounded. A correct memorized fact absent from the
  packet is not a grounded answer. Clearly marked reasoning from the visible
  premise is allowed; new unsupported API behavior is not.
- `citations_valid`: positive factual answers must reference actual evidence IDs
  supporting the claims. An abstention need not cite. Merely valid IDs with no
  supporting text do not count.
- `language_ok`: matches the user's language or the RU-dominant mixed question.
  This is reported separately, not silently substituted for factual correctness.
- Primary success: factually_correct AND grounded AND citations_valid. For
  negative tasks this means a grounded explicit abstention, without a made-up
  value. Report positive and negative denominators separately.

Do not forgive a contradiction because another sentence is correct. Truncated
answers are evaluated as delivered; report token-limit hits separately. Invalid
planner JSON/placeholders are failures with the pre-frozen original-only fallback;
never remove these tasks or hand-correct the queries.

## Interpretation

A/B compare the same fixed model without/with a precomputed warm language hint.
A_packing/B_packing reuse the corresponding saved queries exactly and test only
the old single-host ordering intervention. They are NOT the proposed neighbor
assembly C/D arms. The new multi-host flow ablation is not part of this pilot.
The generic bilingual E control and cold profile delivery were not run here.

Oracle uses exact preselected source excerpts within 800 DTO tokens. No-context
uses the same evidence-only instruction and empty evidence: it is an abstention
control, not an unrestricted test of pretrained model knowledge.

Report the actual unique model invocations, reuse, invalid plans, tokens and
latency. Report per-language and paired per-task/family results. Four families
cannot establish a general success rate or justify product activation. Cases
without retrieval improvement are not evidence that a language-profile detector
is accurate, and detector prose shares are not calibrated probabilities.
