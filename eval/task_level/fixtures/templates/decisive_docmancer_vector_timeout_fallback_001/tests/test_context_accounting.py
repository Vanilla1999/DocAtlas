from docmancer_benchmark.context_accounting import summarize_context_injection


def test_successful_docatlas_retrieval_counts_as_vector_success():
    summary = summarize_context_injection(retrieval_error=None, context_used=True)

    assert summary.to_json() == {
        "status": "success",
        "docatlas_retrieval_status": "success",
        "vector_indexing_timed_out": False,
        "fallback_used": False,
        "fallback_source": None,
        "harness_docatlas_calls": 1,
        "vector_retrieval_success": True,
        "context_used": True,
        "warnings": [],
    }


def test_timeout_fallback_is_not_counted_as_vector_success():
    summary = summarize_context_injection(
        retrieval_error="TimeoutError('DocAtlas context injection exceeded 45 seconds')",
        context_used=True,
    )

    assert summary.status == "fallback_local_project_context"
    assert summary.docatlas_retrieval_status == "fallback_local_project_context"
    assert summary.vector_indexing_timed_out is True
    assert summary.fallback_used is True
    assert summary.fallback_source == "visible_fixture_project_docs"
    assert summary.harness_docatlas_calls == 0
    assert summary.vector_retrieval_success is False
