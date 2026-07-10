# Task 01 — continue bounded architecture refactoring

## Status

Started. The first slice extracted Python manifest and lockfile parsing from `docmancer/docs/project.py` into `docmancer/docs/python_project.py` without behavior changes.

## Goal

Reduce the amount of unrelated code a model must load when changing one ecosystem adapter. Continue with one small extraction: move Node manifest and lockfile parsing out of `ProjectMetadataReader`.

## Required change

Create `docmancer/docs/node_project.py` with one public function:

```python
read_node_project(root: Path, warnings: list[str]) -> tuple[
    dict[str, str],
    list[str],
    list[DependencyObservation],
]
```

Move only Node-related parsing from `docmancer/docs/project.py`:

- `package.json`;
- `package-lock.json`;
- `pnpm-lock.yaml`;
- `yarn.lock`;
- Node source-kind and version helpers.

Keep `ProjectMetadataReader.read()` as the orchestrator.

## Non-goals

- Do not change dependency resolution behavior.
- Do not add Bun support in this refactor.
- Do not rename public classes or fields.
- Do not refactor Cargo, Pub, docs discovery, CLI, or MCP code in the same PR.

## Tests

Run:

```bash
pytest tests/docs/test_project_metadata_reader.py -q
pytest tests/test_exact_version_integration.py tests/test_library_discovery_candidates.py -q
git diff --check
```

## Acceptance criteria

- Existing Node metadata tests pass unchanged.
- `docmancer/docs/project.py` contains no Node lockfile parser implementation.
- `ProjectMetadataReader.read()` output is byte-for-byte equivalent for existing golden fixtures.
- The PR changes only the adapter boundary, imports, and focused tests if necessary.

## Later refactors

After this PR is merged, create separate PRs for Cargo and Pub adapters. Do not extract them in this task.
