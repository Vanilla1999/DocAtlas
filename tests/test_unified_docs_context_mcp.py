"""Split test module; helpers live in _shared_test_unified_docs_context_mcp.py."""
from tests import _shared_test_unified_docs_context_mcp as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})
import ast
import re
import pytest
from tests.docs._scope_guidance_contract import assert_public_context_guidance



























def test_bounded_delivery_records_exact_model_visible_bytes_end_to_end():
    from docmancer.docs.domain.retrieval_routing import new_routing_record, route_initial_stages

    routing = new_routing_record(
        route_initial_stages(
            question="Explain docs", mode="project-only",
            dependency_requested=False, project_doc_items=[],
        ),
        project_docs_used=True,
        dependency_docs_used=False,
    )

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context", "status": "success", "context_available": True,
                "context_pack": [], "trust_contract": {"selected": [], "rejected": [], "risky": []},
                "diagnostics": {"retrieval_routing": routing},
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context", {"question": "Explain docs"},
        cast(Any, Facade()),
    ))

    assert routing["model_visible_bytes"] == len(canonical_projection_bytes(result))
