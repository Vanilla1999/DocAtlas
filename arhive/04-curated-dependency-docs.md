# Curated Dependency Documentation

## What already exists

Docmancer already supports dependency documentation workflows.

Existing behavior includes:

- docs manifests;
- explicit `docs_url` and `docs_url_template` fields;
- version-aware dependency docs;
- Dartdoc/pub.dev documentation support;
- metadata about exactness, binding source, source type, and freshness;
- examples that prefer official API/class pages for key packages.

This roadmap item is not about adding dependency docs support from scratch. It is about reducing low-quality dependency sources.

## What still causes problems

Users may provide broad or weak URLs, for example package landing pages, when an exact official API/class/library page would produce better context.

This can lead to:

- weak context packs;
- missing class-level API details;
- agents overgeneralizing from package summaries;
- confusing dependency docs with project-owned docs.

## What to improve

- Add validation or advisory warnings for broad dependency URLs when an exact docs URL is likely better.
- Improve examples for ecosystems where landing pages are weaker than generated API docs.
- For Flutter/Dart guidance, emphasize `pub.dev/documentation/...` library/class pages over `pub.dev/packages/...` landing pages.
- In context output, make broad/unversioned dependency docs visibly lower confidence than exact/versioned docs.
- Keep project docs and dependency docs clearly separated in user guidance.

## UX acceptance criteria

- Users see a warning or recommendation when they add a broad dependency URL that likely has a better exact docs target.
- Documentation includes good/bad examples for dependency docs URLs.
- Agents prefer exact official API/class pages for key packages.
- Context output makes exact/versioned dependency sources visibly more trustworthy than broad/unversioned ones.
