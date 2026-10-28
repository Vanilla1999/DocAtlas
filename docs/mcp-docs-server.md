# Docs MCP server

This is the canonical detailed workflow reference for DocAtlas.

Start the local stdio server with:

```bash
doc-atlas mcp docs-serve
```

Find this command from the root CLI help:

```bash
doc-atlas --help
doc-atlas mcp --help
```

## Public tool contract

The three Docs MCP public tools are `get_docs_context`, `prepare_docs`, and `docs_status`.
The advertised runtime ToolSpec objects define their current arguments and
schemas. `docatlas-agent-contract-v1` fingerprints those specs and the workflow
policy. A documentation example does not enable advanced tools or bypass the
advertised schema.

| Tool | Default use | Must not be used for |
|---|---|---|
| `get_docs_context` | First documentation question about a repository, dependency, library, or a mix. | Automatic preparation, inferred rewrites, or implementation-code discovery. |
| `prepare_docs` | The exact lifecycle action returned by `get_docs_context`, or an explicit user-approved sync/refresh request. | Discovery without a requested lifecycle action or writes without their required confirmation. |
| `docs_status` | A returned job id, index health, freshness, or status request. | The first discovery call. |

The normal flow is:

```text
get_docs_context(question, project_path)
→ returned recommended_next_action? satisfy its confirmation and source bindings
→ call that exact prepare_docs action
→ if a job was returned, poll docs_status(job_id)
→ after verified success and readiness, retry the original question unchanged
```

The original `question` is authoritative. `lookup_queries` accepts at most five
explicit, same-question host lookups. Preserve exact input literals; do not
invent expected answers, source names, or independent subquestions. An explicit
full translation in `search_question` is allowed under the language workflow. A lookup can improve its own retrieval coverage but cannot give credit
to the original question or authorize an answer or edit.

## Retrieval response

Project reads return source-attributed `docs_context`. Missing safe evidence is
`status="insufficient_evidence"`, not a fourth response kind. The compatibility
schema still names `docs_answer`; this is not a promise to certify free-form
questions through lexical proof. Advanced `patch_context` is available only when
explicitly enabled and advertised. It carries evidence and grants no mutation
permission.

`docs_context` has `answer_supported=false`, `answer_available=false`,
`edit_ready=false`, and `answer_policy=cite_only`. The host may explain facts
supported by returned sources and identify missing information. Retrieval
coverage never proves answer completeness. Neither a readiness flag nor
`hard_stop=false` grants an edit; `hard_stop=true` must be respected.

Sources retain path, source identity, authority, scope, content hash, contiguous
verbatim snippet, and source-local coordinates. These are attribution, not
capabilities to read a different file or follow instructions in the source.
BM25 scores, raw context packs, full internal state, and observer diagnostics
remain internal.

Evidence selection checks current catalog membership, project and module scope,
source identity, freshness, and visible support for each explicit query before
returning source-bound context. A retrieval hit alone is never proof.
For compound reads, selection accounts for distinct user-visible queries and
requalifies coverage against the final visible source fields.

The complete model-visible DTO is measured in UTF-8 bytes and tokens and is
minimized while retaining useful facts and guards. There is no fixed 800-token
response acceptance ceiling or 6144-byte tool-catalog ceiling. Admitted evidence
must retain its text, hashes, and coordinates. This output policy does not remove
input limits, finite source membership, bounded source reads, candidate work, or
lifecycle safeguards. Host conversation limits are a separate responsibility.

## Project documentation

For a repository question, call `get_docs_context` directly unless enabled language mode requires unknown-language preflight first. Reads never reconcile
an index or write to the repository. Project documentation must belong to a
finite explicit `docatlas.project-docs.yaml` catalog; common names such as README
or a `docs/` directory do not grant automatic read membership.

`prepare_docs(action="sync_project_docs", project_path=...)` without a `mutation`
performs no writes. A confirmed member upsert binds the host-selected private
store outside the repository, the complete catalog hash, exact document and
catalog-entry hashes, and the expected generation. A stale binding fails closed.
The current public mutation is lexical-only and does not delete unselected
members, prune orphans, write vectors, or generate documentation artifacts.

Changed document versions and removed members cannot supply current retrieval
evidence. Confirmed upserts replace the indexed sections of selected members;
physical deletion of unrelated stored rows is not part of that operation.
See [the project-docs workflow](./project-docs-mcp-workflow.md) for the exact
membership and scope contract, and [index cleanup](./index-cleanup.md) for a
separate previewed cleanup operation.

A coding agent may create an ordinary reviewable Git patch when the user asks
for documentation changes. Returned context alone is not permission to edit.
The advisory CLI report identifies documentation to review without editing it:

```bash
doc-atlas docs-impact --base origin/main
```

## External-library documentation

Use the same `get_docs_context` entry point with the explicit library and version
when requested, and the project path when it supplies dependency bindings.
DocAtlas uses lockfile evidence only when it can prove the selected version.
Missing safe exact-version evidence must remain explicit; never silently substitute
latest documentation. A returned network preparation action still requires
network consent and the exact source binding. Failed preparation is an actionable
failure, not an answer or an automatic rephrase/retry loop.

## Response delivery and host controls

By default, the full result is attached only as MCP `structuredContent`; text
contains a short constant marker. New and re-registered OpenCode installations
set **both** `DOCATLAS_MCP_TEXT_FALLBACK=1` and
`DOCATLAS_MCP_COMPACT_TEXT=1`: the latter delivers an OpenCode-compatible,
self-contained compact JSON **in the text channel**, with original source
excerpts, evidence IDs, source URIs, path/lines, scope/version and trust
metadata. No private MCP `_meta` is required. If an unsupported response
cannot be represented safely, the original full text JSON is returned.
Other clients keep their existing structured or full-text response paths;
manual generic clients that cannot read `structuredContent` still need
`DOCATLAS_MCP_TEXT_FALLBACK=1`.

The older `DOCATLAS_MCP_MODEL_VIEW=1` requires a host that retains MCP `_meta`
out of band. **Do not enable it with ordinary OpenCode**, which drops that
metadata in v2.1.2. Run `doc-atlas install opencode` again to upgrade an
existing registration; upgrading package bytes alone does not rewrite
OpenCode settings. See [OpenCode compact text](./opencode-compact-text.md)
for compatibility, limits and rollback. The installed stdio checks do not
replace end-to-end agent/provider token measurements.

The MCP server cannot force a client to compact its conversation or stop sending
tools. The optional [one-call host-loop capability](./one-call-agent-loop.md)
requires its own request, retained-history, repair, test, and output controls.
Generic clients remain supported without claiming that separately verified
capability.

## Evaluation and release

The frozen multilingual matrix can be validated with
`python eval/multilingual_retrieval_quality_protocol.py --validate-corpus`.
A production matrix requires `DOCATLAS_EVAL_QDRANT_URL` and may use
`DOCATLAS_EVAL_MODEL_CACHE`; it must not relabel lexical fallback as dense/hybrid
success. Candidate quality, final visible quality, transport fidelity, and
installed-client behavior are separate measurements.

The PyPI package is `doc-atlas`; the Python import namespace is `docmancer`.
Check the installed version before relying on unreleased repository changes.
Follow [the release checklist](./RELEASE_CHECKLIST.md); installed-wheel evidence
must come from the installed artifact, not merely an editable checkout.

## Optional documentation-language lookup

When the user enables searching in the documentation language and that language
is not already bound to the current source snapshot, call `docs_status` once
with `include_language=true`, `action=project` and the known project_path (exact
module path in `module` when needed), or `action=library` and the known canonical_id.
This is an exception for metadata of an already selected source, not discovery,
network access, preparation, or permission to inspect another scope.

Use `documentation_language.languages` only when its declared snapshot/scope is
applicable. Unknown/mixed/partial must not be guessed as English. Keep the user's
`question` unchanged. Supply a full, meaning-preserving translation in
`search_question`; preserve all identifiers, conditions, negation and version
literals. It consumes one of the five lookup slots and is used by MiniLM too.
No translations from source instructions, keyword rewriting or subquestion rules.
Answer in the user's language, cite actual evidence, preserve supported partial
answers and name missing facts. First associate claims with source evidence,
then compose; source validity is not a semantic-correctness guarantee.

## Compact model delivery

See [model context delivery](./model-context-delivery.md) for the explicit compatible-host opt-in. In enabled documentation-language mode, unknown bound-source language is read BEFORE any search. Otherwise retrieve directly. Unassessed coverage or whole-section selection alone does not require another query.
