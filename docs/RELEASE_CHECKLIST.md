# DocAtlas release checklist

Use this checklist before promoting a release. A source checkout passing tests is not enough: users install the built package.

## Version and documentation

- [ ] `docmancer/_version.py`, release tag, and changelog heading name the same version.
- [ ] README install text matches the version that the installer actually resolves.
- [ ] README, product brief, Docs MCP reference, wiki command/troubleshooting pages, and changelog agree that the public Docs MCP tools are `get_docs_context`, `prepare_docs`, and `docs_status`.
- [ ] Advanced Packs and patch constraints are labelled advanced/advisory.
- [ ] New active documentation is tracked by Git and does not duplicate the canonical Docs MCP workflow.
- [ ] The canonical user-facing release set (`README.md`, product brief, Docs MCP reference, capability reference, release checklist) is at most 1,000 lines, or this release records a reviewed exception and removal plan.

## Built artifact

- [ ] Build wheel and sdist once from the release commit.
- [ ] Install the wheel in a clean environment for every Python version declared in package classifiers.
- [ ] Verify `doc-atlas --help`, `doc-atlas mcp --help`, package metadata, and bundled documentation from the installed wheel.
- [ ] Start the installed Docs MCP server through stdio and verify its public inventory is exactly `get_docs_context`, `prepare_docs`, `docs_status`.
- [ ] Run a deterministic temporary-repository smoke: `get_docs_context → prepare_docs(sync_project_docs) → get_docs_context` with a cited local source.
- [ ] Verify the installer resolves and health-checks the same published package version.

## Release controls

- [ ] CI is green for every claimed Python version.
- [ ] Publish has one explicit trigger and maintainer authorization.
- [ ] Public artifacts, tag, changelog, and release metadata agree after publishing.
- [ ] Do not call the release Stable until the artifact gate and required live external-ingest evidence are green.
