# Prompt 04 — Project-aware Docs and Version Resolution

Ты — architect для package ecosystem tooling, dependency resolution и documentation indexing.

## Контекст

Docmancer умеет работать с versioned docs и частично project-aware Flutter/Dart docs:

- читает `.fvmrc` для Flutter hints;
- читает `pubspec.lock` для pub package versions;
- может использовать `project_path`;
- explicit `version` приоритетнее project metadata;
- pub.dev docs можно индексировать через `docs_url_template`;
- Flutter stable/main API docs представлены как разные versions.

Хотим расширить project-aware docs на другие ecosystems и сделать version resolution более надежным.

## Задача

Спроектируй roadmap и technical design для project-aware docs prefetch/version resolution.

## Ecosystems to consider

- Dart / Flutter / pub.dev
- npm / Node.js
- Python / PyPI
- Rust / crates.io
- Go modules

## Что нужно выдать

1. **Target user flows**
   - `prefetch_project_docs(project_path=...)`
   - query docs for dependency from project
   - exact version docs if available
   - best-effort fallback if not available

2. **Ecosystem priority recommendation**
   - Какие ecosystems делать первыми.
   - Почему.
   - Какие отложить.

3. **Manifest/lockfile parsing plan**
   - Flutter/Dart: `.fvmrc`, `pubspec.lock`, `pubspec.yaml`.
   - npm: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `package.json`.
   - Python: `requirements.txt`, `poetry.lock`, `Pipfile.lock`, `pyproject.toml`, `uv.lock`.
   - Rust: `Cargo.lock`, `Cargo.toml`.
   - Go: `go.mod`, `go.sum`.

4. **Version resolution rules**
   - explicit version;
   - lockfile exact version;
   - manifest range;
   - latest fallback;
   - no docs available;
   - non-exact snapshot.

5. **docs_url_template strategy**
   - pub.dev;
   - npm/package docs;
   - PyPI/project docs ambiguity;
   - crates docs.rs;
   - pkg.go.dev.

6. **Registry integration**
   - Как найденные dependencies попадают в registry.
   - Как canonical ids строятся.
   - Как хранить version_source.
   - Как показывать confidence.

7. **MCP API design**
   - `prefetch_project_docs` request/response.
   - `get_library_docs` with `project_path`.
   - warnings and remediation.
   - async job progress.

8. **Ingest/reporting UX**
   - Что показывать пользователю.
   - Как показывать failed packages.
   - Как рекомендовать next actions.

9. **Acceptance criteria**
   - Exact version resolution rates.
   - Useful fallback behavior.
   - Query success criteria.

10. **Test plan**
    - Fixtures per ecosystem.
    - Lockfile parsing tests.
    - Registry integration tests.
    - MCP integration tests.

11. **Implementation plan**
    - Step-by-step.
    - Minimal viable scope.
    - Later expansions.

12. **Risks**
    - Package docs discovery ambiguity.
    - Version mismatch.
    - Lockfile parser complexity.
    - Crawling failures.

## Ограничения

- Не пытайся решить все ecosystems одинаково: у каждого разные docs conventions.
- Приоритет: reliable behavior и clear warnings, а не магическое угадывание.
- Нужно отделить exact docs snapshots от best-effort docs.

## Формат ответа

Дай phased plan: MVP, v1, v2. В конце дай `Must / Should / Could`.
