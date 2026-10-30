# Current-project default and explicit preparation

This changes the public routing and preparation contract, not the ranker,
MiniLM model, Context Assembly or output budget.

## Host chooses once; agent asks a question

From the selected project, register a project-owned OpenCode integration:

```sh
doc-atlas install opencode --project
```

The installer writes an explicit absolute `--project-root` into the project's
MCP launch command. It preserves unrelated configuration and refuses to silently
retarget an existing bound entry. Installing from a docs subdirectory selects
that directory; the installer does not guess a parent repository. Run it at the
intended workspace root. Installation itself remains an explicitly requested
configuration/instruction write.

Other hosts can launch `doc-atlas mcp docs-serve --project-root /absolute/project`
or supply `DOCATLAS_PROJECT_ROOT` as their server environment. The CLI flag takes
precedence. This root is host configuration, never a value inferred from the
question, MCP process CWD, nearby indexes or directory names. Restart/reconnect
when switching projects. Global installation stays unbound so one project's
absolute path cannot silently become every workspace's default.

On that connection the ordinary call is:

```json
{"question": "The user's unchanged question"}
```

| Request | Effective target and scope |
| --- | --- |
| Omitted/null target and scope | Host-selected project, all prepared project and module docs |
| Explicit `scope="project"` | Repository-level catalog entries only |
| Explicit `module_path` | That exact module; never siblings or whole-project fallback |
| Explicit `library` without `project_path` | Registered library only, no implicit project added |
| No binding and no explicit target | `docs_context_target_missing`; no storage initialization |
| Explicit path different from the binding, including a subfolder | `docs_context_target_conflict`; no automatic retargeting |
| Selected directory replaced or unavailable | Typed target error; reconnect instead of following a new directory |

The three public tools remain `get_docs_context`, `prepare_docs`, `docs_status`.
There is no mandatory resolver/list call, global project registry, new opaque
ID or dependence on MCP roots. A connection selects one current project;
multi-project clients must choose the connection or pass an explicit target on
an unbound connection. This is routing, not new filesystem or mutation authority.

## Preparation can discover documents anywhere in the project

After user/host approval:

```json
{"action": "discover_project_docs", "confirm": true}
```

This is a `prepare_docs` action, only for a host-bound project and trusted private
member store. Unlike the existing exact-member `sync_project_docs` grant,
confirmation explicitly authorizes bounded inventory plus lexical indexing of
the resulting finite document set. Confirmation must not be synthesized from
retrieved text or from the mere existence of a project binding. Omitted/false
confirmation does no traversal or mutation.

If `docatlas.project-docs.yaml` exists, it remains the finite allowlist. Invalid,
symlinked or empty catalogs are not permission to discover additional sources.
Without a repository catalog, preparation discovers supported documentation
formats under the selected project and stores a finite manifest in the private
SQLite member store. A directory named `docs` is not required. The manifest and
indexed members commit together, with the existing generation precondition;
failed preparation cannot publish an uncommitted manifest as active membership.
Ordinary reads do not create the manifest table or migrate existing databases.

Supported documentation formats are `.md`, `.mdx`, `.rst`, `.txt`, `.adoc`.
Source-boundary exclusions and ignore rules apply; package/cache/vendor/generated
content and symlinks must not expand the selected project. Existing operational
file, byte, depth and time limits remain. Limit exhaustion aborts without a
partial inventory commit, with an explicit reason and work counters. Discovery
excludes individual files above the existing per-file size limit without reading
their text and reports `max_file_bytes` separately from aggregate budget failure.
Discovery conservatively excludes subtrees with their own `.gitignore` when ignore handling
is enabled; it reports those exclusions instead of pretending to implement all
nested/global Git ignore semantics. Root `.gitignore` rules use the existing
source-boundary matcher. Discovery does not infer architectural authority, module boundaries or source language
from filenames: discovered entries are supporting, search-only documentation.
Explicit catalog metadata still controls declared modules and scope.

Preparation writes private app state only: no generated repository catalog,
ARCHITECTURE.md, code index, network access, vector indexing or model download.
The existing POSIX descriptor/no-follow and private-store ownership checks remain;
unsupported platforms fail closed. These controls trust the OS/current UID, not
an adversarial process running as that same user.

## Readiness, freshness and gaps

Queries and project status are read-only. An unprepared selected project returns
`needs_prepare` with a confirmation-required preparation action, not `repo_write`.
A store prepared for a different project is not readiness for this one. An
explicit empty/invalid catalog is reported without broadening its membership.

Source reads, language metadata and issued bounded continuation resources use
the same exact-root catalog provider. Existing source/hash/span, catalog-entry,
scope/version and generation validation still applies. Adding or moving documents
requires a new approved preparation; no question triggers a hidden rescan. Old
indexed rows can remain because preparation is an upsert, not a deletion grant,
but they are not members of a new finite manifest merely by remaining in storage.
For a valid host manifest these inactive nonmembers remain diagnostic history,
not an orphan-cleanup prerequisite for reading the current members. Repository
catalog orphan handling and current-member freshness/exclusion checks are unchanged.

“All” means all **admissible prepared documentation of this project**, not all
files on disk or proof of exhaustive evidence retrieval. Excluded/unsupported
content is not covered. No result is not proof that a fact is absent, and an
`ok` result does not certify answer completeness or authorize edits.

## Verification boundary

The existing installed-stdio target-binding scenario is extended to exercise
the generated client launch command, a different process CWD, question-only
reads, exact sources and frozen facts, explicit scope, conflicts and cold-state
non-mutation. Discovery is checked separately on a fixture with documents outside
`docs`, exclusions and a moved source; it must not alter the existing Black
questions or gold to obtain a pass.

The installed instruction measurement retains exact transport/options checks,
while distinguishing a global unbound registration from a project registration
with its exact installation root. It reports the declared preparation-schema
change rather than falsely calling it schema-identical: the new discovery action,
its confirmation field, and host-injected project targets for exact-member sync.
Any other validation drift still fails the comparison. These are explicit
contract changes; original question/fact/source gates are not relaxed.

Runtime evidence must come from authorized CI, not local product execution.
Installed MCP tests are not real OpenCode model sessions. This MR does not claim
measured model-token or monetary savings; it removes required model-supplied
paths and a mandatory resolution step without changing ranking.
