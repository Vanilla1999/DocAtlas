# 25 - Snippet-First and Explainable Context

## Goal

Make Docmancer context packs feel immediately useful to coding agents.

Context7 often feels strong because it returns clean code snippets. Docmancer should preserve richer trust metadata while also surfacing directly usable snippets when the query has code/example/test/import/signature intent.

## Snippet-first context packs

For code-oriented queries, each top result should prefer this shape:

```json
{
  "source_class": "dependency_doc",
  "dependency": "FastAPI",
  "url": "https://fastapi.tiangolo.com/tutorial/testing/",
  "heading_path": "Testing > Using TestClient",
  "why_selected": "query asks for TestClient pytest example",
  "snippet": {
    "language": "python",
    "code": "from fastapi.testclient import TestClient\n\nclient = TestClient(app)\n\ndef test_read_main():\n    response = client.get(\"/\")\n    assert response.status_code == 200",
    "why_relevant": "contains TestClient import, client construction, request, and assertion"
  },
  "surrounding_context": "... compact prose with caveats ..."
}
```

## Explain context

Add explainable output for CLI and MCP.

CLI example:

```bash
docmancer context "How should I implement auth here?" --explain
```

Output:

```text
Trusted context for: How should I implement auth here?

Used:
  [project_doc] docs/architecture.md
    why: matched "auth wrapper" project rule
    freshness: current

  [dependency_doc] axum 0.7.5
    why: resolved from Cargo.lock; exact docs.rs URL
    docs_exactness: exact_version_url

Rejected / risky:
  [dependency_doc] latest axum docs
    reason: wrong_version_risk; project resolved axum 0.7.5

  [web] blog post
    reason: unofficial_source; lower confidence than docs.rs

Warnings:
  none

Next actions:
  none
```

## Retrieval/ranking implications

Add or strengthen deterministic signals:

- code/example/test/import/signature intent detection;
- API symbol matches inside snippets;
- snippet language detection when available;
- heading proximity to query terms;
- cap boost so unrelated snippets do not outrank better prose/reference matches;
- preserve exact-version and project-doc trust priority over raw snippet presence.

## Metrics

Add benchmark metrics:

- `snippet_relevance_at_1`;
- `snippet_relevance_at_3`;
- `has_directly_usable_snippet`;
- `snippet_api_symbol_match`;
- `explain_has_selected_sources`;
- `explain_has_rejected_or_risky_sources`.

## Acceptance criteria

- Code-example queries show a directly usable snippet when one exists.
- Snippets include provenance and parent section context.
- Explain output lists selected and rejected/risky sources.
- Snippet boosts do not override wrong-version or low-trust source warnings.

## Non-goals

- Do not synthesize code snippets with an LLM.
- Do not split every code block into an independent document unless benchmark data supports it.
- Do not hide prose/caveats when they are necessary for safe implementation.
