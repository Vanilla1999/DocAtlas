# Task-Level Agent Benchmark Notes

DocAtlas context-injected runs record separate metadata for retrieval status and fallback status:

- `docatlas_retrieval_status`: `success` when DocAtlas retrieval completed; `fallback_local_project_context` when visible project-doc fallback was used.
- `vector_indexing_timed_out`: true only when the retrieval failure was a vector indexing/context timeout, e.g. a message containing `exceeded 45 seconds`, `timed out`, or `timeout`.
- `fallback_used`: true when the benchmark used a fallback context pack.
- `fallback_source`: `visible_fixture_project_docs` for the strict-offline fallback path.
- `harness_docatlas_calls`: 1 only for successful harness DocAtlas retrieval; fallback-only context must not increment this counter.
- `vector_retrieval_success`: true only when retrieval completed without fallback.

Fallback project context may be useful workflow evidence if a patch fairly uses visible docs, but it is not external proof of vector retrieval robustness and must not be counted as vector success.
