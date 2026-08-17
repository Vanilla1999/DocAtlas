# Question planning module

`QuestionPlan` is the bounded question-analysis contract that resolves clauses, subjects, intents, mandatory facets, conditions, and unresolved parts before project evidence may authorize an answer.

`ProjectAnswerRequirementContract` is the one-way boundary that carries those resolved proof obligations from question planning to evidence selection.

## Responsibility

The question-planning module converts a bounded natural-language project-doc question into explicit clauses and proof facets before retrieval evidence is allowed to authorize an answer. Its implementation boundary is `docmancer/docs/domain/question_plan.py` together with the project-answer contract and technical-term normalization modules in `docmancer/docs/domain/`.

The module must fail closed when it cannot resolve a subject or requested operation. It must not invent generic identities such as `project` or `requested operation` that could later be proven by unrelated text.

## Public boundary

The durable output is the project-answer requirement contract: resolved subjects, intents, mandatory facets, conditions, technical identities, parse trace, and unresolved parts. Retrieval ranking is not owned here.

## Relationship to evidence selection

Question planning produces the obligations consumed by the evidence-selection module. **Evidence selection may prove or reject an obligation, but it must not reinterpret the user's question or silently create replacement obligations.** This one-way contract is the architectural seam between the two modules.

## Invariants

- unresolved subjects and operations cannot authorize `supported`;
- compound questions expose every mandatory facet;
- technical aliases are bounded and kind-aware;
- frozen v1–v3 contracts remain compatibility inputs until explicitly migrated.

## Tests

`tests/docs/test_question_plan_v4.py`, project-answer protocol v1–v4 tests, and real MCP probing protect this boundary.
