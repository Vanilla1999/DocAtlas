# Fairness Review: decisive_docmancer_vector_timeout_fallback_001

Source project: `/home/viadmin/StudioProjects/hermes/docmancer`

Sanitized fixture: `eval/task_level/fixtures/templates/decisive_docmancer_vector_timeout_fallback_001/`

Caveat: this task is self-referential to the Docmancer benchmark. If accepted by strict-offline screening, it can support only cautious workflow/regression evidence for fallback accounting and cannot serve as external proof that DocAtlas improves non-Docmancer projects or that vector retrieval is robust.

| hidden requirement | visible source | discoverability | decision |
|---|---|---|---|
| Timeout fallback must use `status` and `docatlas_retrieval_status` of `fallback_local_project_context` | `docs/research/task-level-agent-benchmark.md`, `eval/task_level/execution.py`, public test | yes | keep |
| Timeout fallback must set `vector_indexing_timed_out=true` for timeout/exceeded/timed-out wording | benchmark notes, execution excerpt, public and hidden tests derive from visible wording | yes | keep |
| Fallback must not increment `harness_docatlas_calls` or `vector_retrieval_success` | benchmark notes and execution excerpt | yes | keep |
| Non-timeout fallback still records fallback metadata without setting timeout flag | benchmark notes define timeout-specific flag and generic fallback semantics | yes | keep |
| Successful retrieval path must remain counted as vector success | public pass-to-pass test and source | yes | keep |

No hidden requirement is oracle-only. Requirements are discoverable from issue text, visible project docs/source, public tests, or the visible benchmark source excerpt.
