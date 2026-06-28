from docmancer_benchmark.context_accounting import summarize_context_injection


def test_non_timeout_fallback_preserves_failure_without_timeout_flag():
    summary = summarize_context_injection(retrieval_error="RuntimeError('sqlite database is locked')", context_used=False)

    assert summary.status == "fallback_local_project_context"
    assert summary.docatlas_retrieval_status == "fallback_local_project_context"
    assert summary.vector_indexing_timed_out is False
    assert summary.fallback_used is True
    assert summary.fallback_source == "visible_fixture_project_docs"
    assert summary.harness_docatlas_calls == 0
    assert summary.vector_retrieval_success is False
    assert summary.context_used is False
    assert any("visible project-doc fallback" in warning for warning in summary.warnings)


def test_timeout_detection_accepts_timed_out_wording():
    summary = summarize_context_injection(retrieval_error="vector indexing timed out while building project context", context_used=True)

    assert summary.vector_indexing_timed_out is True
    assert summary.docatlas_retrieval_status == "fallback_local_project_context"
    assert summary.vector_retrieval_success is False
