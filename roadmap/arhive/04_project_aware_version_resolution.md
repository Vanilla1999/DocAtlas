# 04 — Project-aware Docs and Version Resolution Plan

## Goal

Make Docmancer resolve dependency docs based on the actual project context, while clearly separating:

- dependency version resolution;
- docs binding quality;
- docs snapshot exactness.

Core rule:

> Exact package version does not automatically mean exact docs snapshot.

## Priority recommendation

| Phase | Ecosystems | Why |
|---|---|---|
| MVP | Dart/Flutter + Rust | Existing Flutter/Dart support; Rust/docs.rs deterministic |
| v1 | Go + limited npm | Go docs host strong but version resolution nuanced; npm lockfiles strong but docs discovery ambiguous |
| v2 | Python + richer npm | High value but docs discovery and tool landscape ambiguous |

## Target flow

```text
prefetch_project_docs(project_path)
  -> detect ecosystem/workspace
  -> parse lockfiles/manifests
  -> create project dependency observations
  -> bind docs source/version
  -> ingest/register docs entries
  -> get_library_docs(..., project_path) uses project context
```

## Normalized dependency record

Each parser should emit:

```json
{
  "ecosystem": "pub | npm | python | rust | go",
  "package_name": "...",
  "workspace_member": null,
  "dependency_group": "dependencies | dev | optional | peer | build | test",
  "specifier_kind": "exact | range | minimum | git | path | workspace | unknown",
  "specifier_raw": "...",
  "resolved_version": null,
  "version_source": "explicit | lockfile_exact | manifest_exact | manifest_range | manifest_minimum | latest_fallback",
  "source_kind": "registry | git | path | workspace | local",
  "warnings": []
}
```

## Version and docs exactness

### Version precedence

1. Explicit version.
2. Exact lockfile version.
3. Manifest exact pin.
4. Manifest range/minimum.
5. Latest fallback, only if allowed.

### Docs exactness

| Value | Meaning |
|---|---|
| `exact_snapshot` | Immutable docs snapshot |
| `exact_version_url` | URL points to version, but snapshot semantics may vary |
| `best_effort` | Docs inferred from metadata/homepage/README |
| `no_docs` | No binding found |

Do not mark guessed npm/Python docs as exact.

## Ecosystem notes

### Dart / Flutter

- `.fvmrc` for Flutter SDK/channel hint.
- `pubspec.lock` for exact pub dependency versions.
- `pubspec.yaml` for intent/metadata.
- Flutter `stable` / `main` are channels, not exact snapshots.

### Rust

- `Cargo.lock` for exact dependency versions.
- `Cargo.toml` for manifest intent and docs/homepage/repository fields.
- docs.rs adapter is deterministic enough for MVP.
- path/git dependencies get warnings/remediation.

### Go

- `go.mod` has minimum requirements, not npm/Cargo-style full lock.
- `go.sum` is checksum ledger, not selected-version source of truth.
- `replace` must produce warnings.
- pkg.go.dev adapter should be internal/provider-specific.

### npm

- Strong version signals from lockfiles.
- Docs discovery is ambiguous.
- Use stored binding / homepage / README fallback with `best_effort`.
- Preserve scopes like `@scope/pkg`.

### Python

- Lockfiles: `uv.lock`, `poetry.lock`, `Pipfile.lock`.
- `requirements.txt` can be exact, range, VCS, URL, path, constraints.
- PyPI `project_urls[Documentation]` useful, but not guaranteed.
- Strong warning/confidence semantics required.

## MCP API changes

`prefetch_project_docs` should return resolution summary:

```json
{
  "detected_ecosystems": ["rust"],
  "resolution_summary": {
    "dependencies_seen": 84,
    "exact_versions": 79,
    "best_effort_docs": 4,
    "no_docs": 2
  },
  "warnings": []
}
```

`get_library_docs(..., project_path)` should return:

- `resolved_version`;
- `version_source`;
- `version_inferred`;
- `docs_exactness`;
- `docs_binding_source`;
- `confidence`;
- warnings/remediation.

## Acceptance criteria

| Criterion | Target |
|---|---:|
| Exact version resolution on supported lockfile fixtures | ≥95% |
| Go selected/minimum classification | ≥90% correct classification |
| Manifest range never marked exact | 100% |
| Query correct dependency + version on golden tasks | ≥85% |
| Best-effort docs clearly labeled | 100% |

## MVP implementation plan

1. Define normalized dependency record.
2. Harden existing Flutter/Dart reader output.
3. Add Rust parser for `Cargo.lock` / `Cargo.toml`.
4. Add docs.rs adapter.
5. Store project dependency observations.
6. Wire `project_path` resolution into `get_library_docs`.
7. Add CLI/MCP reporting table.
8. Add fixtures and tests.

## Non-goals for MVP

- Universal npm docs resolver.
- Full Python resolver.
- Hosted package registry API dependency.
- Magic docs URL guessing.
- Version diff UX.
