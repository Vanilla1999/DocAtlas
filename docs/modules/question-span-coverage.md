# Question full-span coverage

Question planning is fail-closed. A supported plan is valid only when every
meaningful source character belongs to a parsed clause. Punctuation, whitespace,
and explicit clause connectors may remain between consumed spans; arbitrary
text may not.

## Invariant

For a successful `QuestionPlan`:

1. every atomic frame must match its complete normalized clause;
2. every parsed clause contributes its exact `(start, end)` source interval to
   `QuestionPlan.consumed_spans`;
3. every `PlannedFacet` carries the exact source interval used to create its
   proof obligation;
4. subtracting consumed spans and safe separators from the original question
   must leave no residue;
5. a strict extension is blocked only when a shorter prefix is itself a
   successfully compiled parser-owned frame; legacy-only surfaces remain
   unclaimed and continue through the compatibility adapter.

The splitter is a composition aid, not the safety boundary. Missing a separator
must not turn a parser-owned question into a partial `supported`: complete frame
matching plus exact-prefix ownership probing provide the second line of defence.
Ownership is never inferred from a broad regex prefix list.

## Adding a frame

A new frame must:

- use `fullmatch` or an equivalently end-anchored rule;
- model every free-text field explicitly and reject embedded request heads;
- never add a broad ownership-prefix regex; strict extensions may be claimed
  only when the shorter prefix successfully compiles through the same parser;
- preserve noun coordination inside one clause;
- include positive paraphrase tests, unknown-tail metamorphic tests, and exact
  source-span assertions;
- cover English and Russian forms together when both are public surfaces.

Do not widen an optional `context` group to `.+` merely to accept more phrasing.
Add a typed context grammar or leave the question unresolved.

## Required regression families

At minimum, unknown-tail tests must permute comma, colon, semicolon, period,
question mark, newline, em dash, slash, `and also`, `while also`, discourse
switches such as `by the way`, and a suffix without an explicit question word.
Known compound questions and noun coordination must remain supported.
