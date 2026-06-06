# 13 — Snippet-Aware Ranking

## Problem

Docmancer now detects snippets and reports snippet metrics, but detection happens after retrieval. A code-example query can still rank prose-heavy sections above sections with directly usable code.

Detection proves snippets exist. Ranking must make them useful.

## Goal

Boost sections with relevant code snippets when the query clearly asks for code, examples, imports, tests, signatures, or usage.

The goal is not just `snippet_present@5`; it is better first-page evidence for coding agents.

## Scope

Use existing section metadata:

- `code_snippets`;
- `has_code_snippet`.

Add deterministic ranking signals for query terms such as:

- `example`;
- `usage`;
- `code`;
- `import`;
- `test`;
- `assert`;
- `client`;
- `signature`;
- concrete API symbols.

Preferred behavior:

- boost snippets that contain query API terms;
- boost snippets near matching headings;
- keep attribution to the parent section/source;
- avoid boosting unrelated code blocks just because code exists.

## Non-Goals

- Do not index snippets as independent retrievable units yet.
- Do not add LLM snippet summarization.
- Do not overfit only to FastAPI or Riverpod query IDs.
- Do not hide prose sections when they are more relevant than code.

## Implementation Notes

Add the ranking adjustment late enough that retrieval recall remains unchanged.

Possible approach:

1. classify query as code-example intent;
2. inspect candidate metadata for snippets;
3. boost candidates with snippets containing query terms or API symbols;
4. cap the boost so exact non-code reference pages can still win when appropriate.

The first implementation should be small and deterministic.

## Verification

Add tests for:

- code-example query prefers a result with a matching snippet;
- unrelated snippet does not outrank a more relevant prose/API result;
- FastAPI `TestClient` still ranks the testing tutorial first;
- Riverpod provider example queries surface sections with snippets.

## Success Criteria

- Code-example queries improve snippet relevance in top 3.
- Existing FastAPI and Riverpod Hit@1/MRR do not regress.
- Snippet boosts are explainable from query terms and stored metadata.

## Current Status

Implemented MVP in:

- `docmancer/retrieval/dispatch.py`;
- `tests/test_retrieval_features.py`.

The deterministic intent rerank now adds a snippet-aware boost when a query has code/example/test/import/signature intent and a candidate has `has_code_snippet` or `code_snippets` metadata.

Verification:

```bash
uv run pytest tests/test_retrieval_features.py
```

Covered behavior:

- code-example query prefers a matching snippet result over prose-only reference content;
- existing FastAPI/Riverpod intent rerank tests still pass.

This item is complete for the first snippet-aware ranking MVP.
