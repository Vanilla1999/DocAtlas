# Project-answer surface regression protocol v1

This protocol freezes the bounded natural-language surface contract for Project
Docs question planning. It is not a claim that DocAtlas understands arbitrary
English or Russian. The supported product contract is a reviewed set of semantic
intent families with stable EN/RU surface variants; everything outside that
contract must fail closed with an explicit diagnostic.

`cases.json` contains exactly 100 questions in ten categories. Every case freezes
three things: parser ownership (`question_plan`, `legacy`, or `unsupported`), the
complete proof-obligation signature, and the exact unresolved diagnostics. A
change that keeps the same owner but changes kind, subject, relation, target,
cardinality, response mode, or another proof field therefore fails this gate.
This is deliberate: parser ownership alone is not semantic compatibility.

The EN/RU adapter is bounded and whole-question based. It only rewrites audited
surface families to canonical QuestionPlan questions and then rebinds the result
to the complete original user span. Retrieval cannot use normalization to invent
missing obligations, and an unrecognized tail still makes the question
unsupported.

## Intentional unsupported scope

The corpus intentionally keeps four audited cases outside the supported surface
contract:

- **53** — `Why does clear-index delete remote Qdrant collections?`
- **55** — `Why does clear-index sometimes delete remote Qdrant collections?`
- **58** — `Why are there four storage layers?`
- **72** — the compound Phase 3.1 question listing `RetrievalDispatcher`, the raw
  topic, `EvidenceRequirementSet` hints, and vector/embedding calls.

Cases 53 and 55 omit the closed truth qualifier required by the premise-check
contract; treating them as `always` or `never` would invent user semantics. Case
58 asks for an unbounded cardinality premise over an undefined `storage layers`
set. Case 72 stays unsupported until every listed Phase 3.1 requirement is
represented as an independent proof obligation; the legacy parser currently
covers only a subset, so answering it would reintroduce partial support.

Other deliberately out-of-domain compound/ambiguous questions in the corpus
(for example Bitcoin-price tails and generic `the project` / `the system`
subjects) also remain explicit `unsupported` outcomes. The acceptance target is
**100/100 expected outcomes**, not “100 questions must all receive answers.”

## Run

```bash
python scripts/run_question_surface_gate.py
```

A passing run prints a category summary followed by:

```text
question surface gate: PASS (100/100 expected outcomes)
```
