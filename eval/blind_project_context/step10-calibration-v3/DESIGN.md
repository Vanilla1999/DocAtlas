# V3: final-delivery-conservative calibration

## Policy change, not an output-contract change

V1/V2 required each labeled useful unit to clear the raw admission threshold.
V3 requires every labeled useful **complete own body** and every independent
source fact to occur in the final structurally closed set. Thus a condition
reached from its procedure through an explicit dependency need not itself rank
above the threshold. Direct misses remain reported. Full text, conditions,
scope, source validity, no-answer and emergency50000 requirements are unchanged.
The scoring recipe remains V2's exhaustive min(contextual MaxP, own-body MaxP).
The new calibration recipe is `final-closure-all-useful-breakpoints-v3`, schema2;
it cannot silently replace schema1 V1/V2 policies. Default activation is unchanged.

## Fixed-graph monotonicity review

`minimal_context_structure.close_selection` validates one checked snapshot and
request identity before traversal. A seed adds its own subtree and the own-body
units of ancestors (plus a preamble). Each added body scans its fixed syntax:
reference/footnote definitions add the definition owner's body and ancestors;
authorized, unambiguous anchored links add the target subtree and ancestors.
Only union operations grow `wanted`; edges, anchor ambiguity and checked scope
do not depend on score or the selected seed set. Therefore A⊆B implies
delivered(A)⊆delivered(B). Queue ordering cannot remove a member. Missing edges
remain explicit; no network/source admission is performed by closure.

This is a least fixed point over **typed obligations** (body inclusion versus
subtree expansion). Do not feed every included ancestor back as a new selected
seed: that would expand siblings and change the algorithm. Ordinary idempotence
on untyped seed/body sets is not assumed. Existing ancestor/subtree/dependency
semantics are preserved, including any unavoidable irrelevant ancestor text.

Threshold increase monotonically removes seeds (ties move together), so final
fact/unit retention is nonincreasing, and no-answer contamination cannot grow.
Consequently the **largest retention-feasible breakpoint** is also the best
possible global threshold for the no-answer gate. If it remains contaminated,
no lower threshold can solve that, and higher thresholds lose required output.
The saved adjacent breakpoints provide a concrete infeasibility witness.
Emergency rejection is a separate final public gate, not a monotone success
predicate; an empty error packet must never count as a correct no-answer.

## Evidence boundaries and leakage review

Only the eight existing V2 **calibration** tasks are development inputs.
Their old labels and bytes are preserved and included in the new manifest.
Neither old V2 validation nor T01 supplies calibration examples or breakpoints.
The two new validation families (observatory optics, seed archive), eight tasks,
labels and recipe were frozen under manifest
`00fc5fbe8df385ba5c14a4643e0841a37d16c00de934b2b9bb9b907df3495a14`
before the first V3 inference. They are authored synthetic examples, not an
independent external benchmark; they do not establish broad multilingual or
long-window generalization. Existing long-window calibration remains diagnostic.

The evaluator calls real public prepare/query and instruments the real closure
to replay all score breakpoints. It does not replace retrieval or source checks.
Scorer memo keys contain exact query lanes, complete bodies, heading/ancestor
contexts, identities, model path and scoring options. No threshold sweep invokes
the model. Actual execution/cache/forward/pair counts are saved separately from
logical scorer receipts, avoiding double-counting replay as inference. A final
public policy query, not offline closure predictions, determines delivery PASS.
Validation is run once with frozen policy; failures cannot change labels/tau.

This review is by the implementing agent, not an independent reviewer. Empirical
monotonicity is also checked for every adjacent calibration breakpoint using
the actual delivered evidence-ID sets. All attempts and evaluator corrections
must remain visible; a harness error is neither a product FAIL nor acceptance.
