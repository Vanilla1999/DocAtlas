# Visible benchmark source excerpt for the fixture.

DOCATLAS_CONTEXT_TIMEOUT_SECONDS = 45
FALLBACK_SOURCE = "visible_fixture_project_docs"

def expected_timeout_metadata():
    return {
        "docatlas_retrieval_status": "fallback_local_project_context",
        "vector_indexing_timed_out": True,
        "fallback_used": True,
        "fallback_source": FALLBACK_SOURCE,
        "harness_docatlas_calls": 0,
        "vector_retrieval_success": False,
    }
