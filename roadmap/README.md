# DocAtlas execution roadmap

This is the active product-validation roadmap. It supersedes the earlier infrastructure-construction roadmap without deleting its history. The exact pre-reset roadmap is preserved in Git at commit `d565d8e75af2cbc56bc00fdc9df19dd1ae66863a`; see [`history/README.md`](./history/README.md).

## Product direction

DocAtlas is a **local, version-bound documentation authority and evidence delivery layer for coding agents**.

It keeps reviewable project documentation in Git, derives dependency identity/version evidence from repository state, and returns bounded source-attributed evidence with explicit authority, scope, version binding, support status, and fail-closed recovery.

DocAtlas does not replace source-code search, an LSP, a code graph, tests, static analysis, general web search, or the coding agent itself. Those systems may supply implementation facts or external discovery; DocAtlas adjudicates documentation/version evidence.

The product decision order is:

```text
PUBLIC TRUTH
    ↓
AGENT TRUTH
    ↓
PRODUCT TRUTH
    ↓
CONDITIONAL EXPANSION
```

Infrastructure hardening is no longer the default next step. A new invariant, hash, retrieval stage, or surface must close a demonstrated product risk rather than merely increase internal sophistication.

## Current truth

The following claims are intentionally separate:

| Evidence layer | Current state |
|---|---|
| Deterministic/oracle evidence trajectories | Strong; Agent Developer v1 target contract closes 11/11 |
| Live tool-name selection | Strong signal; Task 21 live gate meets its frozen thresholds |
| Autonomous live evidence trajectory | Not demonstrated; the recorded Agent Developer live result is 0/11 |
| Real coding-task improvement | Not demonstrated; historical Task 23 is formally `INCONCLUSIVE` |
| Context7 parity | Not demonstrated |
| Public release truth for current `main` | Incomplete until a new public release is published and verified |
| Product maturity | **Beta** |

A green deterministic/oracle gate must never be presented as proof that a live coding model can autonomously use the same contract.

---

# P0 — PUBLIC TRUTH

P0 establishes one trustworthy public product before further R&D. During P0, retrieval expansion, public-tool expansion, code-graph work, and benchmark-driven API changes are frozen.

## P0.1 — Remote `main` ruleset: accepted risk

**Status:** `accepted_risk` for the `1.3.0` P0 closure.

On 2026-08-21 the maintainer explicitly chose not to activate remote branch protection for `main`. This is recorded as an operational risk, not misreported as a green protection control.

The canonical optional hardening policy remains in `.github/rulesets/protect-main.json` and `scripts/main_ruleset.py`, so protection can be enabled later without reconstructing the contract.

Compensating release controls:

- a release tag must resolve to a commit reachable from remote `main`;
- PR/release CI remains the reviewed engineering evidence before merge;
- publication remains manual through the `release` environment;
- PyPI publication uses OIDC/Trusted Publishing with no long-lived PyPI token;
- exact public artifacts and installed behavior are verified after publication.

P0 does **not** claim that `main` is protected. The residual risk must remain visible in the P0.6 scorecard.

## P0.2 — Product direction, active roadmap, and release identity

**Status:** this roadmap-reset slice.

Deliverables:

- accepted ADR for the documentation-authority/evidence-delivery direction;
- this short active roadmap;
- explicit release identity: repository `1.2.0` is an unpublished milestone and the next intended public release is `1.3.0`;
- product brief aligned with the new claim boundary;
- regression tests for the direction/release claims.

Acceptance:

- no Stable, Context7-parity, or correct-patch-improvement claim is introduced;
- old roadmap remains recoverable by exact commit identity;
- P0/P1/P2 ordering is machine-checked;
- version bump/publish remains outside this slice.

## P0.3 — Isolate DocAtlas state from the active `docmancer` namespace

Split into two reviewable changes.

### P0.3A — Core identity/state resolver

Target identity:

```text
product:        DocAtlas
distribution:   doc-atlas
CLI:            doc-atlas
primary env:    DOCATLAS_HOME
default home:   ~/.docatlas
primary config: docatlas.yaml
skill identity: docatlas
MCP identity:   docatlas
```

The Python import package may remain `docmancer` until a deliberate 2.0 migration.

Required behavior:

- no implicit writes to `~/.docmancer` on a clean install;
- legacy `DOCMANCER_HOME` and `docmancer.yaml` are compatibility inputs with warnings;
- foreign or ambiguous legacy state fails closed;
- new state has an ownership/schema marker;
- `migrate-home` is preview-first, copy-based, hash-verified, idempotent, and never deletes the source.

### P0.3B — Installer/MCP/skills/config integration

Apply the resolver to CLI, MCP, installer, doctor, clear-index, agent integrations, project config discovery, and release smokes.

Acceptance:

- new installs use only DocAtlas-owned state/integration names;
- old managed DocAtlas entries migrate only when ownership is provable;
- foreign `docmancer` state/skills/MCP entries are never modified;
- uninstall removes only owned DocAtlas integrations.

## P0.4 — Single-source installed agent contract

Keep the public Docs MCP surface at exactly:

```text
get_docs_context
prepare_docs
docs_status
```

Make the runtime public schemas/descriptions the source of truth and add a small machine-readable workflow contract for documentation/tests.

Acceptance:

- public examples validate against the real schemas;
- README/skill/reference agree on the same first-call workflow;
- `prepare_docs` is not advertised speculatively;
- `docs_status` is not advertised as discovery;
- normal-agent docs do not advertise server-owned compatibility arguments;
- installed guidance carries a reproducible contract/schema identity.

## P0.5 — Publish and verify public `1.3.0`

Do not reuse or move a historical `1.2.0` identity. Prepare a new public `1.3.0` release only after P0.3/P0.4 are complete.

Acceptance:

- source version, tag, changelog, wheel, and sdist agree on `1.3.0`;
- PyPI metadata says Beta;
- publication uses the existing OIDC/Trusted Publishing path;
- downloaded public wheel/sdist bytes match gated SHA-256 values;
- a no-cache install of the exact public version passes Docs MCP stdio smoke;
- installed public behavior is verified on Linux, macOS, and Windows;
- the installed public tool inventory is exactly the three-tool contract.

## P0.6 — Public-truth closure scorecard

Maintain [`docs/public-truth-scorecard.md`](../docs/public-truth-scorecard.md) as the single closure record for P0.

Scorecard states are `green`, `pending`, and `accepted_risk`. Branch protection is the one explicitly accepted residual risk for `1.3.0`; it must never be rendered as green. Artifact/public-install rows remain pending until the exact PyPI release exists and post-publish verification completes.

P0 exits when every row is `green` or an explicitly documented `accepted_risk`, no row is `pending`, and product maturity remains honestly **Beta**. An accepted risk does not become evidence that the missing control exists.

---

# P1 — AGENT TRUTH

P1 asks whether a real coding model can acquire the intended evidence through the installed public product.

## P1.1 — Installed-MCP live benchmark harness

Replace surrogate-only conclusions with a benchmark that launches the packaged `doc-atlas mcp docs-serve` over stdio and gives the model the real public tool schemas.

Required evidence:

- exact package/commit/schema identity;
- every attempted tool call, including validation failures;
- bounded repair behavior;
- provider/model/request/token provenance;
- separation of model-format, MCP-schema, server-validation, retrieval, support, and recovery failures.

## P1.2 — Agent Developer 0/11 first-divergence atlas

For each frozen task record:

```text
expected trajectory
actual trajectory
first divergence
model-visible reason
server-side reason
minimal successful repair
failure class
```

Do not change the public API before this analysis identifies repeated failure classes.

## P1.3 — Agent Contract v2 ablation

Candidate simplifications are hypotheses, not pre-approved features:

- `working_path` as host-supplied context;
- server-owned scope/module inference;
- opaque continuation token for returned lifecycle actions.

Compare current contract vs each candidate under the same frozen tasks/model/budgets. Accept only changes that improve schema-valid evidence acquisition without increasing false support or contamination.

## P1.4 — Paraphrase/proofability robustness

Separate candidate discovery from final support adjudication. Expand natural-language robustness while keeping support precision/fail-closed semantics fixed.

Measure exact-identifier, behavior, requirements, policy, typo, alias, and negative-control queries independently.

## P1.5 — Mixed-evidence provenance

Test project policy, module behavior, dependency API, and external advisory sources with conflicting facts. A claim must be supported by an allowed source role, not merely by something in the combined evidence pool.

## P1.6 — Evidence-is-data adversarial gate

Prove that hostile instructions embedded in documentation cannot choose tools, lifecycle actions, authority, credentials, or support status.

---

# P2 — PRODUCT TRUTH

P2 asks whether DocAtlas improves actual coding outcomes.

## P2.1 — Repair the Task 23 methodology

Every task needs:

- a gold-patch positive control;
- an oracle-evidence positive control;
- enforced turn/request/token budgets;
- public and hidden validation;
- immutable starting commit/fixture identity;
- complete token/latency attribution where the provider exposes it.

A task where the gold patch or oracle-evidence control cannot pass is not valid evidence for retrieval/product value.

## P2.2 — Real-repository coding benchmark

Start with a small valid pilot before scaling:

```text
3 repositories
× 8–10 real coding tasks
× 4 evidence conditions
× 3 repeats
× at least 2 models
```

Conditions:

```text
A — repo only
B — repo + DocAtlas
C — repo + external docs (Context7/web)
D — repo/code-context engine + DocAtlas
```

Primary KPI: correct patch/task outcome.

Secondary metrics: unsupported claims, wrong-version claims, cross-source attribution errors, unnecessary/forbidden file touches, tests run/passed, model-visible tokens, total system tokens, tool calls, latency, and time to first edit.

## P2.3 — Stable decision

Stable is an outcome claim, not an infrastructure-count claim.

Promotion requires positive real-agent/product evidence and no unresolved public-truth regression. If DocAtlas does not improve correct-task outcomes or materially reduce unsupported/wrong-version claims at acceptable cost, further retrieval expansion is paused regardless of deterministic test count.

---

# P3 — PRODUCTIZATION / CONDITIONAL EXPANSION

Only after a positive P2 product decision:

1. **Lean primary install profile** — execute the existing Task 24 measurement/split work.
2. **Evidence-envelope interoperability** — consume code/source evidence from host context engines without owning a full code graph.
3. **Onboarding/doctor UX** — make first successful evidence retrieval easy to diagnose.
4. **Context7 parity / external-library expansion** — only if measured coverage is a real bottleneck.
5. **MCP SDK v2 migration** — only for a concrete compatibility/product benefit.
6. **First-party code graph** — only if integration with existing engines is insufficient and a benchmark demonstrates the need.

---

## P0 freeze rule

Until P0 closes, do not merge work whose primary purpose is:

- broader retrieval/reranking;
- a new public MCP tool;
- Context7 parity expansion;
- a first-party code graph;
- relaxing `insufficient_evidence`;
- tuning the historical live benchmark to a target pass rate.

Exceptions require an explicit P0 blocker with evidence that the change is necessary for public truth, identity isolation, contract consistency, or release reproducibility.

## Historical roadmap

The pre-reset implementation roadmap remains part of the audit trail. Use the exact commit referenced in [`history/README.md`](./history/README.md) rather than copying stale historical statuses back into this active roadmap.
