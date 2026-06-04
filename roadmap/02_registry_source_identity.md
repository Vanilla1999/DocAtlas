# 02 — Registry / Source Identity Plan

## Цель

Сделать source identity first-class, чтобы `resolve/query/inspect/versioning` были предсказуемыми для агента и пользователя.

Ключевой инвариант:

> `docs_url` — свойство зарегистрированного source, а не обязательный query payload.

## Core model

Разделить три понятия:

| Concept | Meaning |
|---|---|
| `library` | user-facing lookup token; не primary key |
| `source_id` | versionless identity docs source / locator recipe |
| `canonical_id` | versioned queryable docs target |

Runtime flow:

```text
user input
  -> library/source resolution
  -> source_id
  -> version resolution
  -> canonical_id
  -> indexed docset selection
  -> query
```

## Recommended IDs

```text
source_id    := <ecosystem>:<library_key>:<source_type>
canonical_id := <ecosystem>:<library_key>[@<version_token>]:<source_type>
```

Examples:

```text
pub:go_router:api
pub:go_router@16.2.0:api
flutter:flutter-api@stable:api
web:plugfox:guides
npm:@scope/pkg@1.4.0:api
github:flutter/flutter:repo
```

Implementation status: MVP currently uses a single `doc_libraries` table with source/entry identity columns. The full `docs_sources` / `docs_entries` split remains later work.

## Proposed data model

### `docs_sources`

| Field | Required | Purpose |
|---|---:|---|
| `source_id` | yes | versionless machine id |
| `library` | yes | user-facing handle |
| `normalized_library` | yes | lookup key |
| `ecosystem` | yes | namespace partition |
| `source_type` | yes | web/gitbook/mintlify/github/local/pubdev/flutter_api/dartdoc |
| `docs_url` | conditional | stable root URL |
| `docs_url_template` | conditional | versioned URL renderer |
| `seed_urls` | optional | crawl entry points |
| `allowed_domains` | conditional | crawl boundary |
| `path_prefixes` | optional | subtree boundary |
| `doc_format` | conditional | extraction/parser mode |
| `warnings` | optional | source-level warnings |
| `legacy_ids` | optional | compatibility aliases |

### `docs_entries`

| Field | Required | Purpose |
|---|---:|---|
| `canonical_id` | yes | versioned machine id |
| `source_id` | yes | FK to source |
| `requested_version` | optional | caller/project requested token |
| `resolved_version` | optional | exact version if known |
| `version_source` | optional | explicit, lockfile, .fvmrc, latest, none |
| `version_confidence` | conditional | high/medium/low |
| `version_inferred` | yes | true if not explicit |
| `docs_url_resolved` | conditional | actual query/ingest URL |
| `docs_snapshot_exact` | yes | exactness flag |
| `last_refreshed_at` | optional | freshness |
| `freshness_status` | yes | fresh/stale/never_indexed/refreshing/failed |
| `warnings` | optional | entry-level warnings |

Optional later: `indexed_docsets` for build/snapshot history.

## Version rules

Priority:

1. Explicit exact version.
2. Explicit alias/channel.
3. Project lockfile exact version.
4. Project toolchain hint.
5. Registry alias fallback.
6. Unversioned default.

Important:

- `requested_version` and `resolved_version` must be separate.
- `latest`, `stable`, `main`, `beta`, `next` are aliases/channels, not exact versions.
- Exact dependency version does not automatically mean exact docs snapshot.

## Exactness rules

`docs_snapshot_exact=true` only if:

- locator is immutable;
- `resolved_version` is exact;
- URL points to exact version/tag/commit/equivalent;
- not a moving branch/channel/site.

`false` for:

- `latest`, `stable`, `main`;
- unversioned moving web docs;
- alias routes;
- approximate project metadata;
- mutable channel refresh.

## URL/source resolution

| Situation | Query needs `docs_url`? | Behavior |
|---|---:|---|
| Source registered and unique | no | use stored locator |
| Source registered and URL rendered by template | no | render internally |
| Source unknown | yes unless provider derives | needs registration/input |
| Caller override | explicit only | no silent mutation |

`seed_urls`, `allowed_domains`, `path_prefixes`, `doc_format` are part of source identity/fingerprint because they define the indexed corpus.

## Migration plan

### Phase A — schema extension

Add new fields without behavior change:

- `source_id`
- `canonical_id`
- `normalized_library`
- `requested_version`
- `resolved_version`
- `version_source`
- `version_confidence`
- `version_inferred`
- `docs_url_resolved`
- `docs_snapshot_exact`
- `legacy_ids`

### Phase B — backfill

Automatically backfill:

- normalized library;
- source/canonical ids;
- docs URL resolution;
- freshness status;
- exactness where obvious;
- legacy aliases.

Flag for user action:

- no locator;
- duplicate names/conflicting roots;
- invalid templates;
- domain/path violations;
- lost project context.

### Phase C — resolver switch

Make shared resolver power:

- `resolve_library_id`;
- `get_library_docs`;
- `inspect_library_docs`;
- `refresh_library_docs`.

### Phase D — warning semantics

Limit `needs_docs_url` to true unknown/unrenderable cases.

## Tests

### Unit

- normalization per ecosystem;
- canonical id parse/render;
- version precedence;
- exactness evaluation;
- template rendering;
- validation rules.

### MCP integration

- registered source without `docs_url`;
- ambiguous library/source;
- project-aware version source;
- Flutter stable/main non-exact snapshot;
- stale docset;
- explicit version conflict.

### Migration

- old row with docs_url;
- old versioned row;
- duplicate library names;
- legacy id lookup;
- exact/non-exact backfill.

## MVP vs later

### MVP

- Introduce `source_id` / `canonical_id` in Python model layer, even if DB migration is minimal.
- Make resolver return effective identity and stored locator.
- Do not require full `indexed_docsets` history.

### Later

- Full DB schema split into `docs_sources` and `docs_entries`.
- Content-addressed docset snapshots.
- Version discovery per ecosystem.
- Source/docset health dashboard.
