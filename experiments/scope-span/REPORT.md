# Host scope planning and retained context spans

Date: 2026-09-06. Same branch `fix/context-first-project-reads`, PR #178.
Runtime inspection base: `bf663cb9838fe326579f258cffd05424fa003fbb`.
The final publication parent is recorded by the commit itself; later concurrent
commits are preserved rather than overwritten.

## Findings and minimal implementation

### Scope is a host decision, not an automatic server rewrite

`project_path` identifies the repository. `scope=project` filters to repo-level
sources, rather than meaning every document in that repository. Repository
onboarding and cross-module architecture therefore need `scope=all` without
module filters. An explicit narrower scope remains authoritative, even on a
retrieval miss. `module_path` confines the call to that exact module even when
`scope=all` is supplied. A mixed module-local and repo-policy task uses separate
bounded calls rather than silently widening a module call.

The server's scope routing and filters already implement those boundaries. They
are not changed. Instead, the existing model-facing contract, advertised tool
and scope descriptions, and canonical generated-agent template now explain the
choice explicitly. Three public examples cover repository overview, repo-only
policy and a known module. No default `all`, new tool, language classifier,
automatic retry or new planning service is introduced. The runtime-derived agent
contract identity changes normally when its descriptions/policy change.

This is an executable contract/template publication, NOT a claim that an
independent host model has been tested or forced to follow the policy. Existing
agent instruction files generated before the update must be regenerated through
the normal installer flow to receive the changed canonical template. Runtime
tool descriptions require the client to refresh its loaded tool catalog.

### Table subjects were already protected at the inspected HEAD

The current `context_windows.py` already retains complete pipe-table rows. A
leading cell such as `disabled`, `archived`, `module-only`, or `not approved`
cannot be omitted merely to fit more query terms. If the full row cannot fit,
that row is omitted, not represented by a fabricated suffix. This session does
not reapply or claim new authorship for that existing repair.

New regression cases verify those four subjects plus an end-to-end public table
projection: each snippet is an unchanged contiguous source substring, its line
range matches its source offsets, and the ordinary snapshot/hash/span/budget
validator accepts it. This checks the implemented pipe-table behavior, not a
universal semantic certificate for arbitrary Markdown or prose.

### A new, reproducible expansion loss remained

`_expand_selected_snippets` iterated over a snapshot of the initially selected
sources. After accepting the 160-character candidate, the next round still used
the original source for preservation, qualification and assignment comparisons.
An exact-identifier fact newly added in the first round could therefore vanish
in the second round while the original shorter statement survived.

Reproducer:

- Original: `ALPHA_KEY controls cache state.`
- First accepted span adds `ALPHA_KEY stores disk backups.` before it.
- Later candidate contains the original statement plus memory-buffer details,
  but omits the backup statement.

The minimal application fix refreshes `source = expanded[index]` at the start
of each expansion round. Existing exact/normative preservation checks therefore
protect the latest accepted span, not just the initial one. Its existing union
is still one continuous substring of the same raw source; line ranges are
recomputed, source hashes remain unchanged, and qualification, assignment and
public payload-budget checks still decide whether it can be accepted. Ambiguous
duplicate passages and budget failures retain the existing span.

No new ranking rule, synonym inventory, threshold relaxation, answer claim or
cross-source text splicing is part of this change. The production expansion fix
is one executable line plus two explanatory comments.

## Lightweight DDD and TDD

Read before implementation:

- https://martinfowler.com/bliki/TestDrivenDevelopment.html
- https://martinfowler.com/bliki/DomainDrivenDesign.html
- https://martinfowler.com/bliki/BoundedContext.html

Host intent belongs in the existing MCP/agent contract and generated template.
Contiguous table-window policy remains in the existing domain module. Application
code owns iterative expansion and payload-budget admission. Infrastructure and
public scope normalization remain unchanged; no extra architectural layer is
needed.

The new tests were run before implementation: **10 failed, 11 passed**. The
failures included the missing host scope policy/examples/template guidance and
the actual lost-backup-span assertion. Passing controls covered already-working
scope isolation and table boundaries. The expansion test replaces only window
selection with deterministic contiguous candidates; ordinary requalification and
budget logic still run. It tests orchestration, not model quality.

During work, the remote branch advanced with reports,
`test_host_scope_planning_contract.py` and its inventory, then a basic flat scope
policy and a template scope step. These additions are preserved. The two incoming
scope tests were run unchanged; their existing policy keys remain. This change
adds explicit onboarding/repository identity and public examples, and extends
the existing template step rather than removing it. Publication is based on a
verified later parent, not a force push. Unrelated concurrent changes are not
part of this change's test claims.

## Verification

| Check | Final result |
| --- | --- |
| Existing selected tests before changes | 42 passed |
| New cases before implementation | 10 failed, 11 passed |
| Final focused suite including the incoming scope contract tests | **90 passed** |
| Explicit 95-module documentation run on the verified runtime | **1662 passed, 2 failed** |
| The same two failing checks on pre-change runtime | **Both fail before and after on the compared runtime** |
| Public three-tool catalog | **6116 bytes**, within 6144-byte limit |
| Compile / whitespace / Python module size | PASS |

The initial longer advertised scope guidance exceeded the tool-catalog budget.
It was shortened, not granted a higher limit. Original-question preservation,
lookup limits, module confinement, typed recovery and no edit authorization
remain stated in the final description. The pre-existing exact wording checks
and the concurrently added scope checks both pass.

The two broad-suite failures are explicitly NOT hidden:

1. `test_generic_context_workflows.py::test_wider_windows_preserve_contiguous_witnesses_and_table_qualifiers[16]`
   expects a 520-character ceiling although the pre-existing complete-short-source
   window permits a 583-character source. Its assertion fails on both revisions.
2. `test_model_visible_projection_part02.py::test_docs_context_covered_facet_uses_only_assigned_witness`
   fails to find `docs/proof.md` on both revisions. The assignment-selection issue
   is not fixed or reclassified by this narrow change.

Two modules were not run because `w3lib` is unavailable:
`tests/docs/test_curated_sources.py` and `tests/docs/test_dartdoc_discovery.py`.
The full repository/core/advanced suite, frozen live gates and 15/5/30 usefulness
inventories are NOT claimed as newly passed or measured. Interrupted preliminary
commands are retained in the companion logs and are not counted as successful.

Reproduce focused checks in a normal development environment:

```sh
DOCATLAS_OFFLINE=1 python -m pytest -q \
  tests/docs/test_host_scope_contract.py \
  tests/docs/test_host_scope_planning_contract.py \
  tests/docs/test_context_span_growth.py \
  tests/docs/test_mcp_token_footprint.py \
  tests/docs/test_context_preservation.py \
  tests/docs/test_context_projection_boundaries.py \
  tests/docs/test_context_sentence_windows.py \
  tests/docs/test_mcp_docs_tools_registration.py
```

For the local broad check, enumerate `tests/docs/test_*.py` explicitly, excluding
only the two modules above; the companion JSON records the exact 95 paths. With
all dependencies installed, run the full documentation suite without exclusions.

## Provenance and boundaries

Local execution used an isolated reconstruction from the previously saved git
bundle plus the published changes. The relevant runtime file Git blob hashes
were checked against the remote inspection HEAD before changes; local git
history still starts at the original saved snapshot. This is not a check of the
user's workstation or a claim to a clean exact-HEAD full clone. No user workspace
was modified, no persistent workstation index synchronized, and no model API,
OpenCode or model-weight installation used. Integration tests index temporary
fixtures only.

Only four existing production/template files and the new tests/report are in this
publication. Frozen evaluators, corpus, active witness documents, qualification
thresholds, source identity/lifecycle policy and domain window implementation
remain unchanged. Existing divergent branches, `main`, branch protection and
normal CI workflows are not modified. The new diagnostic shard registers only
this change's tests; prior inventories and expectations are preserved.

## Remaining limitations

Correct scope restores candidate eligibility; it does not guarantee every module
fits in a three-source payload. Retaining a selected span prevents this specific
loss; it does not solve all candidate ranking or unanswered architecture/request-
flow questions. The two pre-existing failing checks still prevent an all-green
claim. Model adherence and wider usefulness need separate measurement. This
commit is a scoped repair, not a declaration that PR #178 is ready to merge.
