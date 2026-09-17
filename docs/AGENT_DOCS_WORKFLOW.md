# Agent documentation workflow

This is the maintained public workflow for coding agents using the DocAtlas documentation server.

The advertised runtime `ToolSpec` objects for the default Docs MCP surface are the source of truth for tool names, descriptions, and schemas. `docatlas-agent-contract-v1` fingerprints those runtime specs plus the workflow policy; installed skills carry the resulting SHA-256 identity so stale guidance is detectable.

## Repository questions

1. For documentation questions and coding or patch tasks, call `get_docs_context(project_path=..., question=...)` before the first edit. The `question` is one concrete documentation question, not a surrounding benchmark, evaluation, or documentation-governance meta-question.
2. If the user provides multiple independent questions, including a benchmark/evaluation list, make separate `get_docs_context` calls. Keep each original question unchanged. For a cross-language question, comparison, conditional scenario, or multiple dependent facets, add 1–3 short `lookup_queries` in the documentation language; a simple single-facet question needs no lookup. Preserve exact identifiers, versions, conditions, negation and both comparison sides. Lookups are retrieval hypotheses for that same question, not a batch channel, an expected answer, or guessed source names.
3. Call `prepare_docs` only from `recommended_next_action`, or when the user explicitly requests documentation lifecycle work such as sync, refresh, index, or prefetch. After preparation succeeds, retry the original `get_docs_context` question unchanged. If a `job_id` is returned, poll `docs_status(action="job", job_id=...)` within a bounded attempt/deadline policy and inspect the terminal result. A running, failed or cancelled job is not readiness; inspect its typed failure/action instead of blindly retrying retrieval.
4. Use `docs_status` only for an explicit health, freshness, index, or background-job status request, or to poll a returned `job_id`, or when `get_docs_context` returns it as `recommended_next_action`; it is not discovery.
5. If the result is `docs_context`, answer only claims directly grounded in its returned sources, cite their paths, and do not claim complete or verified coverage; it never authorizes an edit. If the result is `insufficient_evidence`, do not claim documentation support. Follow at most one non-automatic `rephrase_question` recovery for parser/retrieval uncertainty; if it still fails and `hard_stop=false`, continue repository investigation with local source/tests while keeping the documentary claim unproved. Stop before an edit when `hard_stop=true` or when the task explicitly requires a documentary contract that remains unproved.
6. For a free-form or compound documentation request, the host may provide up to five narrow `lookup_queries`, one concept per lookup, for that same question. `covered_query_ids` and `missing_query_ids` report retrieval coverage; `query_coverage="partial"` must not be presented as complete documentation coverage.

## Formulating a bounded question

Preserve the user's subject, conditions, negation, version and both sides of a comparison. A question about what happens **if** preparation fails is not a request to implement the preparation tool. Keep one coherent comparison/conditional question together; separate genuinely independent questions rather than splitting off its condition. `lookup_queries` may translate or decompose that same question, but must not add an expected answer, a guessed file owner, or an unrelated topic. Never replace the original question with those lookups.

For example, keep `May I use the cached API docs after the lockfile changes?` unchanged; a same-question lookup can be `cached dependency documentation after lockfile version change`, not an invented answer such as `the cache automatically deletes old snapshots`.

## Answering from retrieved context

For `docs_context`, false answer flags mean that the server has not certified an
answer. The host may still synthesize claims directly supported by the snippets.
Preserve useful partial answers, cite their sources, and name the concrete facts
that remain unknown. Retrieval coverage is not semantic completeness.

A source link is optional navigation. Neither a link nor false/unverified flags
alone require opening a file. If a concrete requested fact is missing from an
otherwise relevant excerpt, use an actually available bounded reader, with at
most two extra reads. Stop when sufficient and never reload the same span. Do not
invent a reader when the installed host does not expose one.

## Library and dependency questions

Project documentation is repository-owned evidence scoped by `project_path` and optional `module_path`/`scope`. Library documentation is external-source evidence bound to a library identity and version. Call `get_docs_context(question=..., library=..., project_path=...)` for a current project dependency, or `get_docs_context(question=..., library=..., version=...)` for an explicitly requested exact version.

For current project binding, omit `version`: do not copy it from an earlier response. After a lockfile change, re-query before using dependency evidence. An old cached snapshot or conversation answer is not evidence for the new binding. An explicit historical version must not be presented as current without matching repository evidence.

Network access is opt-in. If documentation must be fetched or refreshed, ask the user and then use the exact `prepare_docs` action returned by `get_docs_context`.

## Patch tasks

Documentation context is evidence, not proof that a patch is correct. Retrieve the required documentation evidence before editing and still run the project's source search, tests, linters, and review after editing.

## Tool boundary

The default Docs MCP surface consists only of `get_docs_context`, `prepare_docs`, and `docs_status`. Normal-agent guidance must use only arguments advertised by the current runtime schemas.

Advanced inspection and patch-contract tools require `DOCATLAS_MCP_ADVANCED_TOOLS=1`. The advanced Packs gateway is a separate surface for explicitly installed API action packs. Neither surface is a static analyzer or a test runner.
