# 21 - Trusted Context Contract

## Goal

Make Docmancer visibly different from docs search.

The product idea:

> Context7 gives docs. Docmancer resolves trusted context.

Every high-level project-context query should return a Trust Contract: a machine-readable explanation of which sources were trusted, why they were trusted, which sources were rejected or risky, and what the agent should do next.

## Problem

Coding agents do not only need relevant text. They need to know whether the text is safe to rely on for the current repository.

Without an explicit trust contract, an agent can still:

- use latest docs for a pinned old dependency;
- ignore local ADRs or architecture docs;
- treat a stale local document as current;
- trust a random docs page over official package metadata;
- miss that retrieval degraded from hybrid to dense-only/lexical-only;
- fall back to WebFetch even though registered local docs exist.

## Contract shape

Target high-level response shape:

```json
{
  "question": "How should I add a Riverpod provider here?",
  "project_path": "/path/to/repo",
  "answer_available": true,
  "context_pack": [
    {
      "source_class": "project_doc",
      "path": "docs/architecture.md",
      "heading_path": "Architecture > State management",
      "freshness": "current",
      "why_selected": "matches local state-management constraint",
      "content": "..."
    },
    {
      "source_class": "dependency_doc",
      "dependency": "flutter_riverpod",
      "requested_version": "project-version",
      "resolved_version": "2.6.1",
      "version_source": "lockfile_exact",
      "docs_exactness": "exact_version_url",
      "docs_binding_source": "pub_dartdoc_template",
      "freshness": "current",
      "why_selected": "resolved from pubspec.lock and exact Dartdoc URL",
      "content": "..."
    }
  ],
  "trust_contract": {
    "trusted_sources": [
      {
        "source_class": "project_doc",
        "path": "docs/architecture.md",
        "freshness": "current",
        "why_selected": "matches local architecture constraint"
      },
      {
        "source_class": "dependency_doc",
        "dependency": "flutter_riverpod",
        "requested_version": "project-version",
        "resolved_version": "2.6.1",
        "docs_exactness": "exact_version_url",
        "why_selected": "resolved from pubspec.lock"
      }
    ],
    "rejected_or_risky_sources": [
      {
        "source": "latest flutter_riverpod docs",
        "reason_code": "wrong_version_risk",
        "reason": "project lockfile resolved flutter_riverpod 2.6.1"
      }
    ],
    "warnings": [],
    "next_actions": []
  }
}
```

## Required fields

### Selected source fields

Each selected source should include as many of these fields as available:

- `source_class`: `project_doc`, `dependency_doc`, `public_doc`, `fallback_doc`, `local_memory`.
- `path` or `url`.
- `title`.
- `heading_path`.
- `dependency`.
- `requested_version`.
- `resolved_version`.
- `version_source`.
- `docs_exactness`.
- `docs_binding_source`.
- `freshness`: `current`, `stale`, `unknown`.
- `retrieval_mode` and degraded mode if applicable.
- `why_selected`.
- `confidence`.
- `token_estimate`.

### Rejected or risky source fields

Rejected/risky entries should include:

- `source` or `source_class`.
- `url`, `library`, or `dependency` when available.
- `reason_code`.
- `reason`.
- `risk_level`: `low`, `medium`, `high`.
- `replacement_source` when there is a safer source.

Example reason codes:

- `wrong_version_risk`;
- `latest_fallback`;
- `unofficial_source`;
- `stale_project_doc`;
- `registry_source_exists`;
- `low_confidence_docs_binding`;
- `locale_mirror`;
- `outside_allowed_domain`;
- `retrieval_degraded`;
- `missing_project_docs`;
- `missing_dependency_docs`.

## Acceptance criteria

- `get_project_context` returns a Trust Contract on every response, even when `answer_available=false`.
- Trusted sources explain why they were selected.
- Wrong-version/latest/unofficial/stale/fallback sources are visible when detected.
- Missing docs become `next_actions`, not dead ends.
- The Trust Contract is compact enough for coding-agent tool output.

## Non-goals

- Do not make Docmancer generate the final natural-language answer.
- Do not invent trust metadata when source/version/freshness is unknown.
- Do not block all context when trust is imperfect; label uncertainty instead.
