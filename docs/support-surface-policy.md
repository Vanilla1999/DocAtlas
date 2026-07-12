# Support surface and maintenance policy

Status: release policy for shipped DocAtlas surfaces. The machine-readable source is `docmancer/support_surfaces.json`; `tests/test_support_surface_policy.py` rejects unclassified CLI commands, Docs MCP tools, and optional extras.

## Support tiers

| Tier | Promise | Test and release policy |
|---|---|---|
| Core | Default local Docs workflow and storage required by it. | Core offline CI is hermetic, release-blocking, and may contact only loopback fixtures. |
| Advanced-supported | Documented opt-in capability maintained by the DocAtlas team. | Offline contracts and shared security checks block release. Provider-specific live checks do not. |
| Maintenance-only | Narrow operational, migration, research, or specialist surface. | Best-effort compatibility. Security and shared-storage regressions block release; feature availability does not determine local Docs MCP health. |
| Deprecated | Compatibility surface with a bounded replacement window. | Tests preserve the compatibility contract until its deadline. Removal requires the declared breaking release and migration notes. |
| Internal | Maintainer implementation or development tooling without a public compatibility promise. | Covered where it shares release-critical code. |

Every non-core inventory entry records its owner, documentation entrypoint, test tier, network dependencies, compatibility promise, removal rule, and failure budget. The owning decision contact is `DocAtlas maintainers` unless an entry is transferred explicitly.

Public service surfaces must also be registered in `SHIPPED_SERVICE_SURFACE_IDS` in `docmancer/support_policy.py`. CI compares that registration boundary with the machine inventory, so a service cannot become supported without an explicit tier decision.

## Failure budgets

- A core retrieval, local SQLite storage, trust-boundary, or shared security regression blocks release.
- An Advanced network outage must not make the local Docs MCP unhealthy. The affected advanced action reports a scoped degraded/error state while `get_docs_context` remains available for local evidence.
- Maintenance-only Qdrant administration/download, USPTO, hosted embedding, crawler, or Packs-provider availability is outside the core health budget. The currently default Qdrant store remains core until Task 24 changes the default backend and install profile.
- Across every tier, shared security and storage regressions block release.
- Live-provider suites are scheduled or manually triggered and advisory; offline contract tests remain required.

## CI tiers

Core offline CI runs `pytest tests/ -m "not advanced and not live and not live_network"` with `DOCMANCER_OFFLINE=1`. The test harness also blocks unregistered outbound DNS and sockets and redirects the hosted registry fallback to loopback. Missing optional artifacts therefore fail locally or produce typed fallback state instead of fetching a hosted registry.

The `advanced-contract` job runs advanced and maintenance contract tests separately. It is still offline and preserves shared security coverage. Real provider tests require an explicit live workflow and must never be added to the core job.

## Deprecation resolutions

The old `doc-atlas add <local-path>` behavior advertised removal after 0.4.x even though the package is now 1.x. It remains compatible through 1.x and is scheduled for removal in 2.0.0; use `doc-atlas ingest <path>`.

The `doc-atlas mcp serve` Packs alias and the legacy `prefetch_project_docs` MCP alias follow the same bounded 2.0.0 breaking deadline. Their replacements are `doc-atlas mcp packs-serve` and `prefetch_project_dependency_docs`/`prepare_docs`, respectively. No deprecated surface may use an unbounded “future release” deadline in the inventory.

## Dependency placement decision

Current core dependencies stay unchanged in Task 29 to avoid an accidental packaging break. Task 24 must move dependencies according to these boundaries:

- Keep local Docs parsing, HTTP policy enforcement, MCP, SQLite/vector fallback, and file-format readers in core until an installation migration is proven.
- Browser and Crawl4AI remain explicit extras.
- Hosted embedding providers remain explicit provider extras.
- Qdrant and FastEmbed are candidates for a vector/maintenance extra because Qdrant administration is maintenance-only; moving them requires installer and default-fallback compatibility tests.
- USPTO parsing uses existing core parsers but the command/service remains maintenance-only; specialist dependencies added later belong in a USPTO extra.

## Documentation placement

Beginner documentation contains only installation and the three-tool Docs MCP workflow. Advanced and maintenance surfaces must link here and state their tier. The inventory is authoritative when prose and CLI help differ; CLI help is labelled from the same inventory at runtime.
