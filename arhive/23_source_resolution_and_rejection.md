# 23 - Source Resolution and Rejection Reasons

## Goal

Make docs discovery trustworthy, not just convenient.

Docmancer should not only say:

> I found this docs URL.

It should say:

> I selected this source because it is official/exact/current, and I rejected or warned about these other sources because they are latest-only, unofficial, stale, locale mirrors, or outside policy.

## Problem

Context7 has a convenient resolve-library-ID flow. Docmancer needs a comparable flow, but with stronger trust semantics.

Agents need:

- fewer manual `docs_url` inputs;
- confidence labels;
- official source preference;
- exact-version preference;
- explicit rejection reasons;
- safe fallback behavior when confidence is low.

## Source confidence ladder

| Source signal | Confidence | Notes |
|---|---|---|
| Existing exact registry binding | Very high | Already accepted and indexed. |
| Lockfile exact version + deterministic docs host | Very high | Example: pub.dev Dartdoc, docs.rs. |
| Official package metadata docs URL | High | Must preserve exactness semantics. |
| Official homepage docs link | Medium/high | Depends on version support. |
| Repository README/docs | Medium | Good fallback but may not be API reference. |
| `llms.txt` / sitemap from allowed official domain | Medium/high | Good public-doc discovery path. |
| Latest docs for pinned dependency | Risky | Include warning/rejection reason. |
| Random blog/tutorial/search result | Low | Do not treat as trusted docs by default. |
| Locale/translation mirror when English canonical exists | Risky | Avoid default top-K contamination. |

## Resolver output

Candidate response shape:

```json
{
  "library": "flutter_riverpod",
  "ecosystem": "pub",
  "project_path": "/path/to/repo",
  "resolved_version": "2.6.1",
  "candidates": [
    {
      "docs_url": "https://pub.dev/documentation/flutter_riverpod/2.6.1/",
      "source_type": "api",
      "confidence": "very_high",
      "docs_exactness": "exact_version_url",
      "why_selected": "pubspec.lock exact version plus pub.dev Dartdoc template"
    }
  ],
  "rejected_or_risky_sources": [
    {
      "source": "https://riverpod.dev/",
      "reason_code": "latest_fallback",
      "reason": "project resolved flutter_riverpod 2.6.1; source appears latest/default"
    }
  ],
  "next_actions": []
}
```

## Selection rules

1. Prefer registered exact sources.
2. Prefer project-resolved versions over user-omitted/latest versions.
3. Prefer deterministic ecosystem docs hosts where available:
   - Pub/Dartdoc for Pub packages;
   - docs.rs for Rust crates.
4. Prefer official package metadata/homepage links over arbitrary web discovery.
5. Use GitHub README/docs as fallback with `best_effort` labels.
6. Ask for a URL when confidence is low instead of guessing silently.
7. Never label guessed npm/Python docs as exact.

## Rejection reasons

Add explicit reasons for not using a source by default:

- `wrong_version_risk`;
- `latest_fallback`;
- `unofficial_source`;
- `low_confidence_docs_binding`;
- `locale_mirror`;
- `outside_allowed_domain`;
- `path_prefix_rejected`;
- `registered_source_exists`;
- `source_stale`;
- `network_fetch_requires_confirmation`.

## Agent policy

When a registered or high-confidence source exists, Docmancer should steer the agent away from direct WebFetch:

```json
{
  "direct_webfetch": "forbidden",
  "reason_code": "registered_source_exists"
}
```

When no safe source exists:

```json
{
  "direct_webfetch": "discovery_only",
  "reason_code": "no_registered_source",
  "next_actions": [
    {"type": "ask_user_for_docs_url", "reason": "No high-confidence official docs source found"}
  ]
}
```

## Acceptance criteria

- Resolver returns selected candidates and rejected/risky sources.
- Exact docs are never claimed for ambiguous docs hosts.
- Latest docs for pinned dependencies are warned or rejected when exact docs are available.
- Agent guidance discourages WebFetch when registered local docs exist.
- Tests cover official exact source, best-effort fallback, latest-version risk, and low-confidence no-source cases.
