# Task 17 — resolve exact dependency identity in real workspaces

## Priority

P1. Source exactness is meaningless if the project version was guessed incorrectly.

## Problem

Current parsers handle more lockfile formats, but workspace importers and duplicate versions can be collapsed or selected implicitly. The first same-name Python package or one root-level Node value is not always the direct dependency of the module being queried.

## Goal

Resolve a dependency version only when the requesting project/module and lock graph prove that identity; otherwise return a structured ambiguity.

## Required changes

1. Add an explicit requester/module identity to dependency resolution where a monorepo can contain multiple importers.
2. For npm, pnpm, Yarn, and Bun:
   - parse current workspace/importer structures;
   - distinguish direct from transitive dependencies;
   - preserve scoped package names and peer/version suffixes;
   - do not let a root importer silently override a child importer.
3. For Poetry, PDM, and uv:
   - follow the direct dependency group/graph when duplicate same-name versions exist;
   - preserve relevant markers/groups;
   - return ambiguity when the lock data cannot bind one version to the requester.
4. Keep all observations for diagnostics. Selecting one exact version must include provenance: manifest, lockfile, importer/group, and resolution rule.
5. Define stable outcomes: `exact`, `compatible_family`, `ambiguous`, `unresolved`, and `conflict`.
6. Bind exact library documentation only for `exact`. Other outcomes require user/model disambiguation and must not fall back to latest silently.

## Required fixtures

- pnpm workspace with different direct versions in root and child;
- npm workspace with one transitive duplicate;
- Yarn/Bun scoped dependency and peer suffix;
- Poetry/PDM/uv lock with duplicate same-name versions and one provable direct edge;
- duplicate case where no edge is provable and ambiguity is required;
- conflicting manifest and lockfile observations.

Use realistic minimized fixtures derived from documented current lock formats. Record the fixture format version.

## Non-goals

- Do not implement source crawling.
- Do not guess from installed site-packages or `node_modules` when lock identity is ambiguous.
- Do not flatten all workspace modules into one dependency map.

## Acceptance criteria

- Every exact result names its requester and lock provenance.
- Root/child and duplicate-version conflicts never select an arbitrary first value.
- Unsupported/ambiguous cases return a bounded next action.
- Existing single-project resolution remains compatible.
- Parser/integration tests and `git diff --check` pass.
