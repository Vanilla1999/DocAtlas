# Project-bound OpenCode integration

Install once from the intended workspace:

```sh
doc-atlas install opencode --project
```

This explicitly binds the local MCP connection to that directory. If the prepared
project lives elsewhere, select it during installation:

```sh
doc-atlas install opencode --project --project-path /absolute/prepared/corpus
```

The project-local `opencode.json` stores `DOCATLAS_PROJECT_BINDING` in
`mcp.servers.docatlas.environment`: canonical absolute `project_path`, the existing
DocAtlas local `project_id`, and the installation `workspace_path`. This is a
connection/workspace binding, not a session ID or authentication credential.
OpenCode's project configuration supplies the connection to sessions, including
sessions in nested directories. Global installation stays unbound. No lookup
target is inferred from the MCP process working directory. Installation binds a
target; it does **not** index documents or assert preparation is complete.

The ordinary call becomes:

```json
{"question": "What is Black's default line length?"}
```

An explicit registered `library` remains a separate library-only request.
Lifecycle/mutation calls still require their own explicit target and authorization.
An explicit different `project_path`, including `corpus/black`, returns
`docs_context_target_mismatch` with the configured binding **before retrieval**.
It does not query the parent, claim insufficient evidence, or suggest creating
documentation. To query another project, install/connect that project's integration.
Relocated or invalid bindings fail with `docs_context_binding_invalid`; reinstall
with the intended existing root rather than falling back to CWD.

## Project versus search scope

`project_path` identifies the indexed project. It is not a directory filter.
`module_path` selects an **existing catalogued module** within that project;
`scope` retains its existing project/module/all meaning. Neither parameter is
an arbitrary documentation-directory filter. A mixed corpus's `black/` directory
must not be passed as a new project or invented module. This change does not add
an arbitrary path-prefix selector or silently broaden an explicit scope.

## Effective settings

`docs_status(action="project")` uses the host binding and returns `project_binding`
and `delivery_configuration` alongside actual project readiness. The latter shows
effective text-fallback/compact-text flags and configured MiniLM model directory;
a configured directory alone does not prove the model loaded or participated.

The installer retains stock OpenCode Code Mode behavior and unrelated settings,
sets the existing compact-text defaults, and persists `DOCATLAS_MINILM_MODEL_DIR`
when supplied as an existing local directory at installation time. It does not
download a model or silently enable a different one.

## Verification boundary

`eval/project_binding/installed_stdio.py --layout unbound|black|mixed` exercises
the installed wheel, actual project installer, stdio MCP, SQLite and MiniLM.
The host-bound layouts check question-only reads, explicit-root parity, rejected
subfolder bindings, source text/coordinates and unchanged source/index state.
The unbound layout retains the missing-target regression. These are deterministic
installed-MCP scenarios, not autonomous OpenCode/model runs or token benchmarks.
