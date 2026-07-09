# Docmancer capabilities

Docmancer is a **local, project-aware, version-aware documentation runtime for coding agents**. It indexes repository docs, monorepo module docs, public docs sites, package references, and private documentation into compact context packs, then serves that context locally through a CLI or an MCP docs server.

The project has two product layers:

1. **Docmancer Docs** — the primary product: local documentation ingest, retrieval, version-aware docs resolution, project docs, compact context packs, and MCP docs tools.
2. **Docmancer Packs** — the advanced layer: version-pinned API action-tool packs for agents that need to call APIs, not only read docs.

## What problem Docmancer solves

Coding agents often answer from model memory, latest-only web docs, repeated WebFetch calls, or unstructured raw pages. That creates several problems:

- answers can be stale or version-wrong;
- the same docs are fetched repeatedly;
- project-specific README/docs/ADR context is ignored;
- monorepo package/app/service docs are hard for agents to target safely;
- raw pages waste token budget;
- private/local documentation is not available to hosted docs services;
- agents do not always know which docs source/version they should trust.

Docmancer solves this by making documentation a local, inspectable, version-aware runtime:

- docs are indexed once and queried many times;
- results are compact sections, not full raw pages;
- every answer can include source attribution and version provenance;
- project docs, module docs, and dependency docs can be queried in the same agent workflow;
- registered sources let agents avoid direct WebFetch once docs are known;
- local hybrid retrieval works without API keys by default.

## Current capability map

This section is a practical map of what Docmancer can do today and which tool or command to use for each job.

| Need | Current capability | CLI / MCP entrypoint | Current boundary |
|---|---|---|---|
| Query local repo docs | Discover, reconcile, stale-check, and query README/docs/wiki/ADR/roadmap files plus module/package docs in monorepos. | `get_docs_context(mode="project")`; lifecycle: `inspect_project_docs`, `prepare_docs(action="sync_project_docs")`; CLI `doc-atlas ingest`, `doc-atlas query`. | Project docs must be indexed before they can be trusted; repo writes still require confirmation. |
| Query a specific module | Use module-aware project-doc filters for packages, apps, services, crates, libraries, and similar module roots. | `get_docs_context(mode="project", module_path=..., scope="module")`. | Module matching is exact; ambiguous module names return structured clarification instead of a guessed answer. |
| Query public docs locally | Fetch, normalize, index, and query public docs sites. | CLI `doc-atlas add`, `doc-atlas query`; MCP `get_docs_context`, `get_library_docs`, `prefetch_library_docs`. | First query requires indexing unless the source is already registered/indexed. |
| Use exact dependency versions | Read supported project metadata and prefetch/query docs for resolved versions. | `get_docs_context(mode="dependency")`, `inspect_project_docs`, `prefetch_project_dependency_docs`, `prefetch_project_docs`, `get_library_docs(project_path=...)`. | Strongest current support is Dart/Flutter and Rust metadata; dependency-docs prefetch may use the network and is separate from project-owned docs ingest. |
| Avoid repeated WebFetch | Register sources once, then query local indexes. | `resolve_library_id`, `get_library_docs`, `list_library_docs`; CLI `doc-atlas list`. | If no registered or confidently resolved docs source exists, user may still need to provide a docs URL. |
| Keep docs private/local | Index local files and private docs without sending content to hosted docs services. | CLI `doc-atlas ingest`; MCP `ingest_project_docs`. | Cloud embedding extras are optional; default retrieval stack can stay local. |
| Get compact context for agents | Return sections with headings, source attribution, extracted snippets, metadata, token estimates, and optional snippet-first presentation for coding queries. | CLI `doc-atlas query`, `doc-atlas context`; MCP `get_docs_context` with `response_style`. | Snippets are extracted from trusted source docs, not synthesized; `context_pack` and Trust Contract remain available. |
| Plan implementation from source evidence | Return a compact implementation map for a patch-like task: relevant files, current behavior, existing dependency APIs, missing symbols, minimal patch path, risks, verification, warnings, and next actions. | MCP `get_patch_plan_context`. | Planning-only surface. It does not replace `get_docs_context`, does not generate a patch, does not index the whole `.pub-cache`, and does not replace `get_patch_constraints` or validation. |
| Compile patch constraints for agents | Return compact, source-attributed project constraints for a coding patch: architecture conventions, forbidden/generated-file edits, source-of-truth rules, pinned dependency contracts, and suggested checks. | MCP `get_patch_constraints`. | Designed to provide actionable project constraints for coding agents; not proven to improve success rate. |
| Validate patch constraints after editing | Deterministically compare caller-supplied constraints with changed files or a patch diff. | MCP `validate_patch_against_constraints`. | Best-effort guardrail only; unknown results require manual review and tests still must run. |
| Run long docs indexing safely | Start async prefetch jobs and poll progress. | `prefetch_library_docs(async=true)`, `prefetch_docs_targets(async=true)`, `get_docs_job_status`. | Large public sites still need sane max pages, allowed domains, and source hygiene. |
| Diagnose docs runtime | Check config, storage, SQLite, Qdrant, indexes, agents, and MCP state. | CLI `doc-atlas doctor`, `doc-atlas qdrant status`; MCP `mcp doctor`. | Doctor output should continue moving toward more explicit severity/fix commands. |

Important current boundary: `get_docs_context(project_path=..., question=..., mode="project"|"mixed")` is the public high-level context tool for combining indexed project-owned docs with optional dependency-doc evidence and a Trust Contract. Project-doc reconciliation stays explicit through `inspect_project_docs` and `prepare_docs(action="sync_project_docs")`; repository writes and dependency network fetches still require confirmation.

Recommended MCP entry point:

```text
get_docs_context(question, project_path?, library?, mode="auto")
```

DocAtlas now provides one high-level MCP entry point for project, library, dependency, and mixed documentation context. Advanced users can still call lane-specific tools directly. Missing library/dependency docs still require explicit network permission; exact-version requests do not silently fall back to latest docs.

For patch-like tasks, keep docs retrieval, implementation planning, constraints, editing, and validation separate:

```text
get_docs_context
→ get_patch_plan_context
→ get_patch_constraints
→ edit
→ validate_patch_against_constraints
```

Use `get_patch_plan_context` after broad docs context when the agent needs an implementation map from source/dependency/design evidence. It can report exact relevant files, missing symbols such as `showBottomDialog: not_found`, dependency APIs such as `PBBottomSheet.open`, a minimal patch path, and verification such as `flutter analyze`. It does not replace agent code reading or constraints validation.

For coding patches that need project rules before editing, use:

```text
get_patch_constraints(question, project_path?, changed_files?, max_constraints=12, max_tokens=1200)
```

This read-only tool compiles deterministic constraints from visible project docs and dependency metadata. It is designed to provide actionable project constraints for coding agents; it does not validate patches and should not be described as proven to outperform repo-only prompting.


### validate_patch_against_constraints — post-edit guardrail

Recommended workflow:

1. Call `get_patch_constraints` before editing.
2. Edit code.
3. Call `validate_patch_against_constraints` with the original constraints plus `changed_files` or `patch_diff`.
4. Fix deterministic violations.
5. Run tests.

The validator detects deterministic issues such as generated-file edits, lockfile edits, provider/UI policy logic where a service/domain/application layer owns behavior, and source-of-truth layer edits. It is deterministic best-effort: it does not prove correctness, does not replace tests, does not call an LLM, and is not evidence that DocAtlas improves coding-agent success.

### get_patch_constraints — expanded deterministic heuristics

`get_patch_constraints` now recognizes more deterministic project-rule patterns while keeping cautious source attribution. It scans visible architecture docs, ADRs, contributing guides, root/module READMEs, and maintained docs for language such as `must`, `must not`, `should`, `owned by`, `belongs to`, `source of truth`, `canonical`, `single source`, `do not duplicate`, `do not bypass`, layer ownership, repository/adapter ownership, and provider delegation.

The compiler can extract owner/source-of-truth instructions from statements like `PermissionService owns permission policy`, `policy belongs in PermissionService`, or `Provider delegates to PermissionService`. It also recognizes generated-artifact guardrails for `*.g.dart`, `*.freezed.dart`, protobuf generated outputs, `*.generated.*`, `generated/`, `dist/`, regeneration/source-model instructions, and `build_runner` references.

Dependency constraints are derived only from visible manifest/lock metadata with deterministic versions, including Dart/Flutter, Python, JS/TS, Rust, and Go files where supported. Task keywords and `changed_files` improve ranking and suggested checks, but they do not create high-confidence invented owners or dependency versions without source evidence.

Snippet-first presentation is additive. For example:

```json
{
  "question": "How do I use FastAPI Depends?",
  "response_style": "snippet-first"
}
```

`auto` selects snippet-first for coding, API, command, and config questions when selected trusted chunks contain usable snippets. `auto` remains evidence-first for conceptual architecture or release-history questions.

## Core capabilities

### 1. Local documentation ingest

Docmancer can index documentation from local files and directories:

```bash
doc-atlas ingest ./docs
doc-atlas ingest ./README.md
doc-atlas ingest ./runbooks --include "*.md"
```

Supported local formats:

| Format | Notes |
|---|---|
| Markdown / `.md` / `.markdown` | Heading-aware chunking. |
| Text / `.txt` | Paragraph and sliding-window chunking. |
| HTML / `.html` / `.htm` | Readability-based extraction. |
| PDF | `pypdf` first, fallback to `pdfplumber`; page numbers captured. |
| DOCX | `python-docx`; heading styles mapped to Markdown levels. |
| RTF | `striprtf`; paragraph splits. |

Useful ingest controls:

- `--include <glob>` — include only matching paths;
- `--exclude <glob>` — exclude matching paths;
- `--format <format>` — restrict to specific formats;
- `--recursive / --no-recursive` — control traversal;
- `--skip-known` — skip unchanged content;
- `--recreate` — rebuild an index;
- `--no-vectors` — FTS5-only ingest without embeddings/vector upsert.

### 2. Public docs site indexing

Docmancer can fetch and index documentation from public URLs:

```bash
doc-atlas add https://docs.pytest.org
doc-atlas add https://fastapi.tiangolo.com/
doc-atlas add https://github.com/org/repo
```

Supported URL provider types:

| Source | Strategy |
|---|---|
| GitBook | Uses `/llms-full.txt`, then `/llms.txt`. |
| Mintlify | Uses `/llms-full.txt`, `/llms.txt`, then sitemap. |
| Generic web docs | Generic crawler for non-GitBook/non-Mintlify sites. |
| GitHub repos | Fetches README and docs Markdown. |

Useful add controls:

- `--provider auto|gitbook|mintlify|web|github`;
- `--strategy llms-full.txt|sitemap.xml|nav-crawl`;
- `--max-pages <n>`;
- `--browser` for JS-heavy sites;
- `--recreate`.

### 3. Semantic section indexing

All sources follow the same indexing pipeline:

1. fetch or read content;
2. normalize it into Markdown-like text;
3. split it into semantic sections based on heading structure;
4. store sections in SQLite with title, heading path, source URL/path, content hash, and token estimate;
5. index section text and titles with SQLite FTS5;
6. optionally embed sections and upsert dense/sparse vectors into local Qdrant;
7. write extracted Markdown and JSON to disk for inspection.

This means results are returned as relevant sections, not full pages.

### 4. Inspectable local storage

Docmancer keeps data local and inspectable.

Default locations:

| Path | Purpose |
|---|---|
| `~/.docmancer/docmancer.yaml` | Global configuration. |
| `~/.docmancer/docmancer.db` | Global registry and metadata. |
| `~/.docmancer/docs-indexes/` | Per-library SQLite indexes. |
| `~/.docmancer/extracted/` | Extracted Markdown + JSON sections. |
| `~/.docmancer/qdrant/` | Managed local Qdrant binary, storage, metadata, logs. |
| `~/.docmancer/models/` | FastEmbed model cache. |
| `~/.docmancer/embeddings-cache/` | Content-hash-keyed embedding cache. |
| `./docmancer.yaml` | Optional project-local config. |

The storage root can be overridden with:

```bash
DOCMANCER_HOME=/some/path
```

### 5. Per-library index isolation

Each library/version can have its own independent index under `~/.docmancer/docs-indexes/`. This avoids cross-library contamination and allows independent refresh/removal for each target.

Benefits:

- separate docs snapshots by library and version;
- safer refresh and deletion;
- fewer irrelevant hits from unrelated libraries;
- lightweight global registry metadata.

### 6. Local retrieval modes

Docmancer supports multiple retrieval modes:

| Mode | Description |
|---|---|
| `lexical` | SQLite FTS5 / BM25-style full-text retrieval. Strong for API names, config keys, flags, error strings, and identifiers. |
| `dense` | Dense embedding retrieval through local Qdrant or fallback vector store. |
| `sparse` | SPLADE sparse vector retrieval. |
| `hybrid` | Fans out across lexical, dense, and sparse signals, then fuses ranks with Reciprocal Rank Fusion. |

Example:

```bash
doc-atlas query "How do I parametrize a pytest fixture?" --mode hybrid --explain
```

`--explain` shows which signal placed a result, for example `lexical#1`, `dense#3`, `sparse#2`.

### 7. Public-doc retrieval quality checks

Docmancer includes a small repeatable public-doc benchmark lane for checking retrieval quality against saved artifacts.

Current benchmark artifacts cover:

| Suite | Queries | Current Docmancer status |
|---|---:|---|
| Riverpod | 5 | `Hit@1=1.0`, `Hit@5=1.0`, `MRR=1.0`, locale contamination `0.0`, snippet present@5 `1.0`. |
| FastAPI | 3 | `Hit@1=1.0`, `Hit@5=1.0`, `MRR=1.0`, locale contamination `0.0`, snippet present@5 `1.0`. |

The benchmark lane also stores normalized Context7 snapshots for the same Riverpod and FastAPI suites, so Docmancer and Context7 artifacts can be checked offline with the same expected query IDs and metric fields.

Regression checks currently validate:

- Docmancer public-doc artifacts for Riverpod and FastAPI;
- Context7 snapshot shape and comparability;
- `Hit@1`, `Hit@5`, and `MRR` regression gates;
- snippet presence and locale-contamination metrics;
- matching query IDs between golden datasets, Docmancer artifacts, and Context7 snapshots.

Important limitation: Context7 snapshots are normalized saved artifacts, not live Context7 recaptures. This makes the comparison reviewable and repeatable offline, but live Context7 recapture is still a future benchmark-hardening task.

### 8. Local Qdrant lifecycle

Docmancer can manage its own local Qdrant process for vector retrieval.

Commands:

```bash
doc-atlas qdrant up
doc-atlas qdrant status
doc-atlas qdrant logs
doc-atlas qdrant down
doc-atlas qdrant upgrade
```

Capabilities:

- downloads a pinned Qdrant binary when needed;
- starts Qdrant in the background with telemetry disabled;
- tracks pid, port, URL, health, and ownership metadata;
- refuses to stop or delete resources it does not own;
- supports external Qdrant through `DOCMANCER_QDRANT_URL`;
- supports air-gapped/pre-staged binary through `DOCMANCER_QDRANT_BINARY`.

### 9. No API keys required by default

The default retrieval stack uses local FastEmbed embeddings and local Qdrant. No OpenAI, Voyage, Cohere, or other API key is required.

Optional cloud embedding extras exist:

| Extra | Enables |
|---|---|
| `docmancer[embeddings-openai]` | OpenAI embeddings. |
| `docmancer[embeddings-voyage]` | Voyage embeddings. |
| `docmancer[embeddings-cohere]` | Cohere embeddings. |

If a configured cloud provider lacks an API key, Docmancer can fall back to FTS5-only with a warning instead of failing the ingest.

### 10. Compact context packs

`doc-atlas query` and MCP docs tools return compact context packs:

- top matching sections;
- heading paths;
- source URLs or file paths;
- version/source metadata;
- token estimates;
- optional adjacent sections or full-page expansion.

Example:

```bash
doc-atlas query "How do I authenticate?" --budget 2400
doc-atlas query "How do I authenticate?" --expand
doc-atlas query "How do I authenticate?" --expand page
doc-atlas query "How do I authenticate?" --format json
```

Docmancer reports token efficiency on queries:

- compact context-pack tokens;
- raw full-page docs token estimate;
- percent saved;
- agentic runway multiplier.

This makes the cost of documentation context visible to agents and developers.

### 11. Source registry

Docmancer keeps a persistent registry of known documentation sources. A source can be registered once and then queried later without repeating the docs URL.

The registry tracks:

- library name;
- ecosystem;
- source type;
- version;
- docs URL or URL template;
- requested/resolved version;
- whether the docs snapshot is exact;
- aliases and legacy IDs;
- refresh status and errors;
- full target spec such as seed URLs, allowed domains, and path prefixes.

Identity levels:

| Identity | Purpose |
|---|---|
| `source_id` | Library/source identity without version. |
| `canonical_id` | Version-pinned identity. |
| `library_id` | Current canonical lookup identity. |

The lookup cascade supports exact IDs, canonical IDs, legacy IDs, normalized name + ecosystem + version + source type, aliases, and partial matches.

### 12. Version-aware dependency docs

Docmancer can inspect project metadata to resolve docs versions from the project itself.

Supported metadata currently includes:

| File | What it provides |
|---|---|
| `.fvmrc` | Flutter SDK version or channel. |
| `pubspec.lock` | Exact Pub package versions. |
| `pubspec.yaml` | Direct dependencies and version specifiers. |
| `Cargo.toml` | Rust dependency declarations. |
| `Cargo.lock` | Exact Rust dependency versions. |

This enables workflows like:

- query docs for the exact `flutter_riverpod` version in `pubspec.lock`;
- avoid latest-only documentation when the project is pinned to an older version;
- prefetch dependency docs for a project before a coding task;
- expose version provenance on every docs response.

Use `prefetch_project_dependency_docs` for this dependency-docs prefetch flow. The older compatible tool name `prefetch_project_docs` does the same thing, but despite the name it does not ingest project-owned README/docs/wiki files.

Every docs response can include:

- `requested_version`;
- `resolved_version`;
- `version_source`;
- `docs_snapshot_exact`;
- `docs_exactness`;
- `docs_binding_source`;
- confidence metadata.

#### Exact-version behavior

DocAtlas now exposes explicit exact-version status and prevents silent latest-doc fallback:

**Exact-version status codes:**

- `exact_version_indexed` — exact version docs successfully indexed and queried
- `exact_version_not_supported` — library does not provide per-version docs
- `exact_version_fallback_latest` — exact version unavailable, latest docs used (explicitly marked)
- `exact_version_empty_index` — exact version indexed but contains no content
- `exact_version_resolution_failed` — could not resolve exact-version docs URL

**Python library support (minimal):**

For Python packages where reliable versioned docs URL patterns can be determined:

- **FastAPI**: Does not provide per-version docs; returns `exact_version_not_supported` with fallback to latest
- **Click**: Provides major.x docs, not patch-level; returns `exact_version_not_supported` with major-version fallback
- **Pydantic**: Provides major-version docs (v1/v2), not patch-level; returns `exact_version_not_supported` with major-version fallback

When exact-version docs are unavailable, DocAtlas returns structured status with specific reason codes rather than silently using latest docs.

### 13. Pub Dartdoc and docs.rs support

For ecosystem docs, Docmancer supports versioned documentation URL templates such as:

```text
https://pub.dev/documentation/{library}/{version}/
https://docs.rs/{library}/{version}/
```

For Pub/Dartdoc targets, Docmancer can discover precise seed URLs from package documentation index pages, including class, library, and entity pages. This reduces crawling noise and makes exact-version API docs more practical.

#### Official docs fallback for Dart/Flutter packages

For high-value Dart/Flutter packages, Docmancer provides automatic official docs discovery:

- **riverpod / flutter_riverpod** → `riverpod.dev` (concept guides, provider docs, modifiers)
- **flutter_bloc / bloc** → `bloclibrary.dev` (concept guides, architecture, tutorials)
- Packages without known official docs fall back to pub.dev API reference

Behavior:

- When `resolve_library()` or `get_docs()` is called for a known Dart/Flutter package without explicit `docs_url`, Docmancer auto-registers the official docs source with high confidence.
- Official guide docs are preferred over pub.dev API reference because they provide conceptual explanations, usage examples, and best practices needed by coding agents.
- Packages with only pub.dev URLs (e.g., `go_router`) are not auto-registered and return `needs_docs_url` as before.
- Ecosystem aliasing is supported: `flutter`, `dart`, and `pub` are all treated equivalently.
- Dartdoc diagnostics (`dartdoc` key) are included in `DocsResult.diagnostics` when a Dart/Flutter package is queried.

### 14. Project-owned docs discovery

Docmancer can discover and index docs that belong to a repository, not just external library docs.

Project docs candidates include:

- `README.md`;
- `ARCHITECTURE.md`;
- `CHANGELOG`;
- `CONTRIBUTING`;
- `SECURITY`;
- `LICENSE`;
- `docs/`;
- `doc/`;
- `wiki/`;
- `adr/`;
- `roadmap/`;
- `runbooks/`.

For monorepos, module docs are also discovered under common module parent directories:

| Parent directory | Module type |
|---|---|
| `packages/*` | package |
| `apps/*` | app |
| `services/*` | service |
| `modules/*` | module |
| `libs/*` | library |
| `crates/*` | crate |
| `plugins/*` | plugin |
| `components/*` | component |

Within each module root, Docmancer looks for maintained docs such as `README*`, `ARCHITECTURE*`, `CHANGELOG*`, `CONTRIBUTING*`, `docs/`, `doc/`, ADR folders, and runbook folders. Module docs are tagged with `doc_scope="module"`, `module_id`, `module_name`, `module_path`, and `module_type`; root repository docs remain `doc_scope="project"`.

Excluded by default:

- `.git`;
- virtual environments;
- dependency directories;
- build directories;
- caches;
- source code that is not a reviewable docs candidate.

### 15. Project docs staleness detection

Project docs are hashed and tracked. Docmancer partitions them into:

| State | Meaning |
|---|---|
| Current | Indexed and content hash/mtime still match. |
| Stale | Indexed but file changed; re-index recommended. |
| Ignored | Indexed before but no longer discovered. |

When docs are stale, MCP responses include stale indicators and recommended next actions instead of silently relying on outdated context.

### 16. Agent-discoverable project onboarding

The project docs tools are designed so an agent can guide itself:

1. call `inspect_project_docs(project_path=...)` for read-only discovery;
2. discover README/docs/wiki/roadmap/ADR candidates and dependency metadata;
3. inspect `project_docs.modules` and `project_docs.indexed_modules` when the question is module-specific;
4. if docs are not indexed, follow `reason_code = project_docs_found_not_indexed` and call `prepare_docs(action="sync_project_docs")`;
5. if docs are stale, follow `reason_code = project_docs_stale` and call `prepare_docs(action="sync_project_docs")`;
6. if no docs exist, follow `reason_code = no_project_docs`, ask the user, and have the coding agent create a reviewable `ARCHITECTURE.md` only after confirmation;
7. if docs exist but no high-level overview/architecture doc is found, follow `reason_code = architecture_doc_creation_recommended` and ask before creating `ARCHITECTURE.md`;
8. then answer repo-specific questions with `get_docs_context(mode="project")`;
9. for module-specific questions, prefer `module_path="packages/backend"` plus `scope="module"`; if a module name is ambiguous, ask the user to choose instead of guessing.

Project-docs responses include `reason_code`, `next_action`, optional `next_actions` / `recommended_next_actions`, `requires_confirmation`, `confirmation_reason`, `arguments_patch`, and optional agent/user messages so agents can follow the flow without guessing. Module-specific failures use structured reason codes such as `module_not_found`, `module_ambiguous`, and `no_module_docs`.

This avoids generic answers when the repo already documents its architecture or conventions.

### 17. Docs MCP server

Docmancer exposes its docs runtime through MCP:

```bash
doc-atlas mcp docs-serve
```

Agents can then resolve, fetch, refresh, prefetch, inspect, and query docs without leaving their tool loop.

Core library docs tools:

| Tool | Capability |
|---|---|
| `resolve_library_id` | Resolve a library from registry or explicit docs URL. |
| `get_library_docs` | Resolve, ingest/refresh if needed, then query local docs. |
| `refresh_library_docs` | Refresh a library/version. |
| `prefetch_library_docs` | Download/index one or more versions ahead of time. |
| `inspect_library_docs` | Inspect one exact docs target. |
| `remove_library_docs` | Remove one docs target. |
| `prune_library_docs` | Prune old targets with dry-run support. |
| `list_library_docs` | List registered docs. |

Project docs tools:

| Tool | Capability |
|---|---|
| `inspect_project_docs` | Discover project docs and dependency metadata. |
| `ingest_project_docs` | Index reviewable project docs. |
| `bootstrap_project_docs` | Safely inspect, ingest/refresh existing reviewable docs, and inspect again; stops before repo writes or dependency network fetches. |
| `get_project_docs` | Query project-owned docs and return structured remediation when docs are missing, stale, not indexed, unmatched, or module-ambiguous; supports `module`, `module_path`, and `scope`. |
| `get_project_context` | Return a repo-grounded context pack with a Trust Contract, project docs, and one exact dependency-doc source when requested/detectable; supports `mode` values `auto`, `project-only`, `deps-only`, and `public-docs`, plus `module`, `module_path`, and `scope`. |
| `prefetch_project_docs` | Historical name for prefetching exact dependency docs from manifests/lockfiles; not project-owned docs ingest. |
| `prefetch_project_dependency_docs` | Clear alias for `prefetch_project_docs`; prefer this name in new agent instructions. |

Manifest and batch tools:

| Tool | Capability |
|---|---|
| `validate_docs_manifest` | Validate `docmancer.docs.yaml`. |
| `prefetch_docs_manifest` | Validate and prefetch manifest targets. |
| `prefetch_docs_targets` | Prefetch explicit targets with seed URLs, allowed domains, path prefixes, max pages, browser mode, etc. |

Job tools:

| Tool | Capability |
|---|---|
| `get_docs_job_status` | Poll a docs indexing/prefetch job. |
| `list_docs_jobs` | List jobs by status. |
| `cancel_docs_job` | Cancel a running job. |

### 18. Async prefetch and job tracking

Prefetch operations can run asynchronously. Jobs track:

- status: pending, running, succeeded, partial, failed, cancelled;
- phase: validating, resolving, fetching, indexing, done;
- timestamps;
- total/completed/failed targets;
- current target and URL;
- discovered/fetched/indexed pages;
- completed/failed chunks;
- ordered events.

This lets agents start large documentation indexing work and poll progress instead of blocking indefinitely.

### 19. `docmancer.docs.yaml` manifests

Docmancer supports batch docs declarations through a manifest:

```yaml
version: 1
defaults:
  source_type: api
  allowed_domains:
    - docs.example.com
targets:
  - id: my-lib
    library: my-lib
    version: "2.1.0"
    docs_url: https://docs.example.com/my-lib/2.1/
    allowed_domains:
      - docs.example.com
  - id: project-dep
    library: some-dep
    ecosystem: pub
    version: project-version
    project_version:
      package: some-dep
      fallback: latest
```

Manifest validation checks:

- structure;
- duplicate IDs/canonical IDs;
- URL security;
- allowed domains;
- source types;
- project-version resolution.

### 20. URL security and WebFetch policy

Remote URLs pass through security validation:

- only `http` and `https` schemes;
- private network, loopback, link-local, multicast, and localhost addresses rejected;
- host must match `allowed_domains` when specified;
- path must match `path_prefixes` when specified.

Docmancer also returns machine-readable docs policy for agents:

```json
{"direct_webfetch": "forbidden", "reason_code": "registered_source_exists"}
{"direct_webfetch": "discovery_only", "reason_code": "no_registered_source"}
```

This steers agents away from repeated WebFetch when a registered local source exists.

### 21. CLI setup and agent integration

Docmancer can install agent-facing skill/config files:

```bash
doc-atlas setup
doc-atlas setup --profile agent --agent claude-code --yes
doc-atlas install <agent>
```

Supported install targets include Claude Code, Cursor, Codex, Cline, Claude Desktop, Gemini, GitHub Copilot, and OpenCode.

The goal is that agents know when to call Docmancer before relying on model memory or WebFetch.

### 22. Diagnostics and doctor

Docmancer includes health checks:

```bash
doc-atlas doctor
doc-atlas mcp doctor
doc-atlas qdrant status
```

Diagnostics cover areas such as:

- config and database availability;
- SQLite FTS5 support;
- index/source counts;
- installed agent skills;
- Qdrant process state;
- MCP pack SHA verification;
- credential resolution;
- actionable next steps.

Doctor is also the first-run boundary check for docs workflows: it should make clear what is local storage, what may fetch from the network, which indexes are stale or degraded, and which command fixes the issue.

### 22a. Install, backup, restore, and private-doc posture

Supported setup path:

```bash
python -m pip install docmancer
doc-atlas setup
doc-atlas doctor
doc-atlas mcp docs-serve
```

For agent integrations, verify installation with the target agent's config plus:

```bash
doc-atlas list
doc-atlas doctor
```

Backup/restore is file-based because Docmancer keeps state local and inspectable. To move or restore state, copy the active `DOCMANCER_HOME` directory, plus any project-local `docmancer.yaml` files. The default home contains:

| Path | Include in backup | Notes |
|---|---|---|
| `~/.docmancer/docmancer.yaml` | yes | global config |
| `~/.docmancer/docmancer.db` | yes | registry and metadata |
| `~/.docmancer/docs-indexes/` | yes | per-library SQLite indexes |
| `~/.docmancer/extracted/` | yes | extracted Markdown/JSON review artifacts |
| `~/.docmancer/qdrant/` | optional/yes if using hybrid | local vector storage, binary metadata, logs |
| `~/.docmancer/models/` | optional | FastEmbed model cache; can be redownloaded |
| `~/.docmancer/embeddings-cache/` | optional | can be recomputed |
| `./docmancer.yaml` | yes | project-local config |

Restore checklist:

1. install the same or newer compatible Docmancer version;
2. copy the backed-up `DOCMANCER_HOME` to the target machine;
3. copy project-local `docmancer.yaml` files with their repos;
4. run `doc-atlas doctor`;
5. run `doc-atlas list` and one representative `doc-atlas query` or `doc-atlas context` command;
6. if Qdrant paths or vector state changed, run `doc-atlas qdrant status` and refresh vectors if doctor reports drift.

Private-doc security guidance:

- default lexical retrieval is local and does not require cloud API keys;
- use OS disk encryption or an encrypted volume for private docs and indexes;
- keep `DOCMANCER_HOME` outside shared/synced folders unless that is intentional;
- review optional cloud embedding providers before enabling them, because document text may be sent to the provider;
- keep credentials in the OS keychain or environment-specific secret manager, not in indexed docs;
- use URL allowlists and path prefixes for explicit public/private docs targets;
- SQLCipher-style encrypted SQLite indexes are not enabled by default; use filesystem encryption today if index-at-rest encryption is required.

Release integrity posture:

- prefer package-manager installs from the documented release channel;
- pin versions for reproducible agent environments;
- verify downloaded pack artifacts by SHA-256 where pack install commands expose hashes;
- treat arbitrary docs URLs as untrusted until they pass Docmancer URL validation and source review;
- rerun `doc-atlas doctor` after upgrades.

### 23. Advanced retrieval configuration

Docmancer supports advanced retrieval behavior through `docmancer.yaml`:

- hierarchical retrieval: retrieve documents first, then sections inside selected documents;
- query-aware routing: regex-based routing to metadata filters such as API docs paths;
- adjacent/page expansion defaults;
- retrieval mode defaults;
- vector store settings;
- token budget defaults.

This is useful for large docs portals and mixed corpora where different query patterns should prefer different subsets.

### 24. Update, refresh, inspect, and remove workflows

Docmancer supports lifecycle management:

```bash
doc-atlas list
doc-atlas inspect
doc-atlas update
doc-atlas update https://docs.example.com
doc-atlas remove <source>
doc-atlas remove --all
```

For MCP docs targets, the equivalent capabilities are available through `list_library_docs`, `inspect_library_docs`, `refresh_library_docs`, `remove_library_docs`, and `prune_library_docs`.

### 25. Offline and repeated-query workflow

After the initial ingest/prefetch, docs are local. That enables:

- repeated queries without repeated crawling;
- offline docs access;
- lower warm-query latency;
- reproducible snapshots;
- private/internal docs workflows;
- less token waste from repeated raw WebFetch pages.

This is one of Docmancer's main differentiators from hosted public-docs lookup tools.

## End-to-end examples of current behavior

### Example 1 - Query local project docs

Use this when the repository already has `README.md`, `docs/`, `wiki/`, ADRs, runbooks, or architecture notes.

CLI flow:

```bash
doc-atlas ingest ./docs
doc-atlas ingest ./README.md
doc-atlas query "How should authentication work in this project?" --explain
```

MCP flow:

```json
{
  "tool": "bootstrap_project_docs",
  "arguments": {
    "project_path": "/path/to/repo",
    "question": "How should authentication work in this project?"
  }
}
```

If you need the lower-level flow, start with `inspect_project_docs`. If docs are found but not indexed or stale, the response includes a structured `reason_code` and `next_action` such as:

```json
{
  "reason_code": "project_docs_found_not_indexed",
  "next_action": {
    "type": "ingest_project_docs",
    "tool": "ingest_project_docs"
  },
  "requires_confirmation": false,
  "arguments_patch": {"project_path": "/path/to/repo"}
}
```

After ingest:

```json
{
  "tool": "get_project_context",
  "arguments": {
    "project_path": "/path/to/repo",
    "question": "How should authentication work in this project?",
    "tokens": 3000
  }
}
```

Typical returned evidence includes:

```json
{
  "title": "Authentication architecture",
  "source_class": "project_file",
  "path": "docs/architecture.md",
  "heading_path": "Architecture > Authentication",
  "stale": false,
  "content": "..."
}
```

What this gives an agent:

- local project rules instead of generic library advice;
- exact file paths and headings for review;
- stale warnings when indexed docs changed;
- recommended next actions instead of silent failure.

### Example 2 - Query public docs locally

Use this when the agent needs public library docs but should avoid repeated raw WebFetch.

CLI flow:

```bash
doc-atlas add https://fastapi.tiangolo.com/
doc-atlas query "How do I raise HTTPException with status_code and detail?" --mode hybrid --explain
```

MCP flow:

```json
{
  "tool": "get_library_docs",
  "arguments": {
    "library": "FastAPI",
    "ecosystem": "python",
    "source_type": "web",
    "docs_url": "https://fastapi.tiangolo.com/",
    "topic": "raise HTTPException with status_code and detail",
    "tokens": 3000
  }
}
```

After the source is registered, later calls can omit the URL if registry resolution is unambiguous:

```json
{
  "tool": "get_library_docs",
  "arguments": {
    "library": "FastAPI",
    "ecosystem": "python",
    "topic": "TestClient example with pytest assertions",
    "tokens": 3000
  }
}
```

Typical returned evidence includes:

- canonical URL or source path;
- page title and heading path;
- compact section content;
- version/source metadata when known;
- token estimates and expansion options;
- retrieval explanation when requested.

### Example 3 - Project-aware dependency docs

Use this when the correct answer depends on versions in the current project, not latest docs.

Example project signals:

```text
pubspec.lock      -> exact Pub versions
pubspec.yaml      -> direct Dart/Flutter dependency declarations
Cargo.lock        -> exact Rust versions
Cargo.toml        -> Rust dependency declarations
.fvmrc            -> Flutter SDK channel/version hint
```

MCP flow:

```json
{
  "tool": "inspect_project_docs",
  "arguments": {"project_path": "/path/to/flutter_app"}
}
```

The inspection response can show dependency metadata:

```json
{
  "dependency_sources": {
    "manifests_found": ["pubspec.yaml"],
    "lockfiles_found": ["pubspec.lock"],
    "exact_versions_available": true,
    "dependency_next_action": {
      "type": "ask_user_to_prefetch_dependency_docs",
      "tool": "prefetch_project_docs",
      "alias_tool_after_confirmation": "prefetch_project_dependency_docs",
      "requires_confirmation": true,
      "confirmation_reason": "network_fetch"
    }
  }
}
```

After approval for network docs fetching:

```json
{
  "tool": "prefetch_project_dependency_docs",
  "arguments": {
    "project_path": "/path/to/flutter_app",
    "include_flutter": true,
    "include_dart": true,
    "continue_on_error": true
  }
}
```

Then query a dependency using project context:

```json
{
  "tool": "get_library_docs",
  "arguments": {
    "library": "flutter_riverpod",
    "ecosystem": "pub",
    "project_path": "/path/to/flutter_app",
    "topic": "autoDispose provider keepAlive lifecycle for this project version",
    "tokens": 3000
  }
}
```

The important metadata is version provenance:

```json
{
  "library": "flutter_riverpod",
  "requested_version": "project-version",
  "resolved_version": "2.6.1",
  "version_source": "lockfile_exact",
  "docs_exactness": "exact_version_url",
  "docs_binding_source": "pub_dartdoc_template",
  "confidence": "high"
}
```

This is the main way Docmancer avoids latest-only answers when a repository is pinned to an older dependency.

### Example 4 - Project docs plus external library docs

Use this when the answer needs both local architecture rules and external API behavior.

Current workflow:

1. Inspect and ingest project-owned docs.
2. Query project docs for local rules.
3. Query library docs for API details.
4. The agent combines both evidence sets in the final answer or code change.

Example:

```json
{
  "tool": "get_project_docs",
  "arguments": {
    "project_path": "/path/to/repo",
    "query": "state management rules provider wrappers autoDispose",
    "tokens": 2000
  }
}
```

Then:

```json
{
  "tool": "get_library_docs",
  "arguments": {
    "library": "flutter_riverpod",
    "ecosystem": "pub",
    "project_path": "/path/to/repo",
    "topic": "autoDispose FutureProvider example for resolved project version",
    "tokens": 3000
  }
}
```

The agent should combine the two result sets like this:

```text
Project rule:
- docs/architecture.md says feature screens must use app provider wrappers.
- docs/state-management.md says screen-scoped async providers should be autoDispose.

Dependency docs:
- flutter_riverpod resolved from pubspec.lock.
- The versioned docs explain the provider lifecycle and keepAlive behavior.

Implementation decision:
- Use the project wrapper module.
- Use an autoDispose async provider.
- Do not copy latest-only examples if they conflict with the resolved version.
```

Current boundary: `get_project_context` can return project-doc and one dependency-doc evidence set in one Trust Contract, but agents should still run `bootstrap_project_docs` or `inspect_project_docs` first and follow any returned confirmation gates before relying on the combined context.

### Example 5 - Async prefetch for large docs work

Use this when the agent should start indexing several docs sources without blocking the whole task.

```json
{
  "tool": "prefetch_library_docs",
  "arguments": {
    "library": "FastAPI",
    "ecosystem": "python",
    "versions": ["latest"],
    "source_type": "web",
    "docs_url": "https://fastapi.tiangolo.com/",
    "async": true
  }
}
```

Poll progress:

```json
{
  "tool": "get_docs_job_status",
  "arguments": {"job_id": "..."}
}
```

The job status tracks phases such as validating, resolving, fetching, indexing, and done. It also reports discovered/fetched/indexed page counts and failures.

### Example 6 - Batch docs manifest

Use this when a repo wants reviewable docs targets checked into version control.

`docmancer.docs.yaml`:

```yaml
version: 1
defaults:
  source_type: web
targets:
  - id: fastapi
    library: FastAPI
    ecosystem: python
    docs_url: https://fastapi.tiangolo.com/
    allowed_domains:
      - fastapi.tiangolo.com
  - id: project-riverpod
    library: flutter_riverpod
    ecosystem: pub
    version: project-version
    project_version:
      package: flutter_riverpod
      fallback: latest
```

Validate only:

```json
{
  "tool": "validate_docs_manifest",
  "arguments": {
    "manifest_path": "/path/to/repo/docmancer.docs.yaml",
    "project_path": "/path/to/repo"
  }
}
```

Prefetch:

```json
{
  "tool": "prefetch_docs_manifest",
  "arguments": {
    "manifest_path": "/path/to/repo/docmancer.docs.yaml",
    "project_path": "/path/to/repo",
    "continue_on_error": true,
    "async": true
  }
}
```

### Example 7 - Inspect, refresh, and remove docs targets

Use this for lifecycle management after docs are indexed.

List registered sources:

```json
{
  "tool": "list_library_docs",
  "arguments": {"stale_only": false, "limit": 50}
}
```

Inspect one exact target:

```json
{
  "tool": "inspect_library_docs",
  "arguments": {"canonical_id": "pub:flutter_riverpod@2.6.1"}
}
```

Refresh:

```json
{
  "tool": "refresh_library_docs",
  "arguments": {
    "library": "FastAPI",
    "ecosystem": "python",
    "version": "latest",
    "force": false
  }
}
```

Remove:

```json
{
  "tool": "remove_library_docs",
  "arguments": {"canonical_id": "python:FastAPI@latest"}
}
```

### Example 8 - URL security and safe explicit targets

Use explicit target prefetch when the docs site needs seed URLs, path restrictions, or browser mode.

```json
{
  "tool": "prefetch_docs_targets",
  "arguments": {
    "targets": [
      {
        "library": "example-lib",
        "ecosystem": "js",
        "version": "1.2.0",
        "source_type": "web",
        "docs_url": "https://docs.example.com/example-lib/1.2/",
        "seed_urls": ["https://docs.example.com/example-lib/1.2/getting-started"],
        "allowed_domains": ["docs.example.com"],
        "path_prefixes": ["/example-lib/1.2/"],
        "max_pages": 200,
        "browser": false
      }
    ],
    "continue_on_error": true,
    "async": false
  }
}
```

Docmancer validates remote URLs and rejects unsafe targets such as loopback, private network, link-local, multicast, unsupported schemes, or domains outside the allowed list.

### Example 9 - Public-doc quality regression checks

Current saved benchmark artifacts let the project check whether public-doc retrieval regresses.

```bash
uv run pytest tests/test_context7_snapshot_benchmark.py tests/test_public_docs_regression_gate.py
```

Current saved suites:

- Riverpod: 5 queries;
- FastAPI: 3 queries.

The tests check Docmancer artifacts and normalized Context7 snapshots for matching query IDs, Hit@1/Hit@5/MRR, snippet presence, and locale contamination.

### Example 10 - Current high-level orchestration boundary

`get_docs_context` is the shipped high-level context-pack tool, but it deliberately does not silently perform every setup action. Agents should still use `inspect_project_docs` and, when needed, `prepare_docs(action="sync_project_docs")` first:

```text
get_docs_context(project_path=..., question=..., mode="project"|"mixed")
  -> query indexed project docs
  -> optionally query one requested/detected exact dependency-doc source
  -> return one compact Trust Contract with selected/rejected/risky sources
  -> include warnings and next_actions for missing, stale, or non-exact docs
```

It does not create repository docs, silently ingest stale project docs, or prefetch dependency docs from the network. Those actions remain explicit through `next_action`, `arguments_patch`, and confirmation gates.

## Docmancer Packs capabilities

Docmancer Packs are the advanced product layer for API action tools.

They are separate from the docs retrieval flow: users can get value from Docmancer Docs without installing packs.

### 1. Version-pinned API packs

Install a pack:

```bash
doc-atlas install-pack open-meteo@v1
doc-atlas mcp serve
```

Each pack includes artifacts such as:

- `contract.json`;
- `tools.curated.json`;
- `tools.full.json`;
- `auth.schema.json`;
- `provenance.json`;
- manifest with SHA-256s.

Every artifact is SHA-256 verified before install.

### 2. Tool Search pattern

Regardless of how many packs are installed, the Packs MCP runtime exposes two meta-tools:

| Tool | Purpose |
|---|---|
| `docmancer_search_tools` | Search across installed pack tool surfaces. |
| `docmancer_call_tool` | Dispatch a selected tool call. |

This avoids flooding the MCP tool list with hundreds or thousands of API operations.

### 3. Pack source standards

Docmancer can compile or represent packs from:

| Source standard | Pack behavior |
|---|---|
| OpenAPI 3.0 / 3.1 | HTTP executor with auth, headers, encoding, idempotency. |
| Swagger 2.0 | OpenAPI-like HTTP tool surface. |
| GraphQL introspection JSON | Queries as read-safe operations, mutations as destructive operations. |
| TypeDoc JSON | Documentation-only `noop_doc` operations. |
| Sphinx `objects.inv` | Documentation-only `noop_doc` operations. |
| `python_import` | Optional subprocess callable execution, gated by `--allow-execute`. |

### 4. Safety gates for API calls

Before dispatching a pack call, Docmancer runs a gate chain:

1. resolve tool slug;
2. validate args with JSON Schema;
3. resolve credentials;
4. block destructive operations unless installed with `--allow-destructive`;
5. block executable operations unless installed with `--allow-execute`;
6. inject/reuse idempotency keys for non-idempotent operations when declared;
7. percent-encode path parameters safely;
8. redact logs so argument keys are recorded, not values.

This makes API action tools safer for coding agents.

## Typical workflows

### Workflow A — local docs query

```bash
doc-atlas setup --profile cli-docs --yes
doc-atlas ingest ./docs
doc-atlas query "How do we authenticate?" --explain
```

Use when the project already has local docs and you want grounded answers from those files.

### Workflow B — public docs site query

```bash
doc-atlas add https://docs.pytest.org
doc-atlas query "How do I parametrize a fixture?" --mode hybrid
```

Use when the agent needs public docs locally instead of repeatedly fetching web pages.

### Workflow C — MCP docs for agents

```bash
doc-atlas setup --profile mcp-docs --yes
doc-atlas mcp docs-serve
```

Then an agent can call `get_library_docs`, `inspect_project_docs`, or `get_project_docs` directly.

### Workflow D — project-aware dependency docs

1. Agent calls `inspect_project_docs(project_path=...)`.
2. Docmancer discovers docs files and lockfiles.
3. Agent asks before network prefetch if dependency docs are needed.
4. `prefetch_project_docs` indexes exact dependency docs.
5. `get_library_docs(project_path=...)` answers from the project-specific versions.

Use when dependency version matters.

### Workflow E — project-owned docs + external library docs

1. `inspect_project_docs` discovers README/docs/ADR/wiki and dependency metadata.
2. `prepare_docs(action="sync_project_docs")` indexes/reconciles project docs when needed.
3. `get_docs_context(mode="project")` retrieves project conventions.
4. `get_docs_context(mode="library"|"mixed")` or `get_library_docs` retrieves external library docs when explicitly needed.
5. Agent combines both in the answer or code change.

Use when the correct answer depends on local architecture and external API behavior.

### Workflow F — API action pack

```bash
doc-atlas install-pack some-api@v1
doc-atlas mcp serve
```

Use when the agent should call an API through a version-pinned, schema-validated MCP tool surface.

## Strengths compared to generic web/docs lookup

Docmancer is not trying to be only a hosted public-doc catalog. Its strongest capabilities are local and project-aware:

- exact project dependency versions;
- private and local docs;
- project-owned README/docs/ADR context;
- offline/repeated docs access;
- inspectable extracted content;
- token-aware context packs;
- source attribution and version provenance;
- MCP-native next actions for agents;
- repeatable public-doc regression checks;
- safe API pack dispatch.

Public-doc lookup tools can be faster for one-off latest-doc questions, but Docmancer is designed for coding agents working inside a real repository with real docs, real lockfiles, and repeated docs needs.

## Current known gaps and improvement areas

The current benchmark work against Context7 closed the first small public-doc retrieval gap on the saved Riverpod and FastAPI suites. The remaining work is about making that comparison broader, more automatic, and more representative of Docmancer's project-aware wedge:

- add a single high-level project-context workflow/tool that automatically combines project-owned docs and dependency docs instead of requiring the agent to orchestrate multiple calls;
- improve docs-source discovery so agents need fewer manual `docs_url` inputs for known packages;
- broaden public-doc benchmarks beyond Riverpod and FastAPI;
- automate live Context7 recapture where tool access is available;
- keep improving top-K source diversity across more docs sites;
- make snippet-aware ranking and snippet selection more first-class, not only measured after retrieval;
- strengthen eval reporting for degraded hybrid retrieval;
- add exact-version Dartdoc benchmarks from `pubspec.lock`;
- add exact-version docs.rs benchmarks from `Cargo.lock`;
- add project-owned-docs plus dependency-docs benchmarks;
- add forbidden-version scoring for exact-version suites.

These are roadmap/eval items, not changes to the core product direction.

## Capability summary

| Area | Capability |
|---|---|
| Local ingest | Markdown, text, HTML, PDF, DOCX, RTF. |
| Web ingest | GitBook, Mintlify, generic web, GitHub, browser fallback. |
| Indexing | Semantic sections, SQLite FTS5, extracted Markdown/JSON. |
| Retrieval | Lexical, dense, sparse, hybrid, RRF, explain mode. |
| Public-doc eval | Saved Docmancer and Context7 artifacts, Riverpod/FastAPI regression gates, snippet and locale metrics. |
| Vectors | Local FastEmbed + local Qdrant; no API keys by default. |
| Context packs | Compact results, source attribution, token savings, expansion modes. |
| Registry | Persistent docs source identity, aliases, versions, refresh status. |
| Version awareness | `.fvmrc`, `pubspec.lock`, `pubspec.yaml`, `Cargo.toml`, `Cargo.lock`. |
| Project docs | Discover, ingest, query, stale-check README/docs/wiki/ADR/roadmap and monorepo module docs. |
| Project-aware workflow | Query project docs, module docs, and dependency docs with `bootstrap_project_docs`, `get_project_docs`, and the shipped `get_project_context` context-pack tool. |
| MCP docs | Resolve/query/refresh/prefetch/list/inspect/prune docs through MCP. |
| Manifests | `docmancer.docs.yaml` validation and batch prefetch. |
| Jobs | Async docs indexing jobs with status/progress/cancellation. |
| Security | URL validation, WebFetch policy, local ownership checks. |
| Agent integration | Setup/install skill files for major coding agents. |
| Diagnostics | `doctor`, inspect, status, stale indicators, next actions. |
| Packs | Version-pinned API tools, Tool Search, safety gates, SHA verification. |

## Bottom line

Docmancer's core value is giving coding agents documentation context from **the sources and versions the project actually uses**. It is most useful when docs need to be local, private, version-aware, project-aware, token-efficient, inspectable, and available through an MCP tool loop.
