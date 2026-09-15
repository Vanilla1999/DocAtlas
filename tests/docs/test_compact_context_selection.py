"""Regression cases for compact direct-evidence selection."""
from __future__ import annotations

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens


UUID_DIRECT = (
    "Note that we are looser when validating data from JSON in strict mode. "
    "For example, when validating a `UUID` field,\ninstances of `str` will be "
    "accepted when validating from JSON, but not from python:"
)
UUID_CODE = """```python
import json
from uuid import UUID
from pydantic import BaseModel, ValidationError

class Model(BaseModel):
    value: UUID

data = {'value': '12345678-1234-1234-1234-123456789012'}
try:
    Model.model_validate(data, strict=True)
except ValidationError as exc:
    # From Python, a string is not a UUID instance.
    print(exc)

json_data = json.dumps(data)
# From JSON in strict mode, the UUID string is accepted.
print(Model.model_validate_json(json_data, strict=True))
""" + "# Complete runnable example keeps additional setup and output context.\n" * 15 + "```"

HTTPX_DEFAULT = (
    "HTTPX is careful to enforce timeouts everywhere by default.\n\n"
    "The default behavior is to raise a `TimeoutException` after 5 seconds of\n"
    "network inactivity."
)
HTTPX_POOL = (
    "* The **pool** timeout specifies the maximum duration to wait for acquiring\n"
    "a connection from the connection pool. If HTTPX is unable to acquire a connection\n"
    "within this time frame, a `PoolTimeout` exception is raised. Additional pool\n"
    "configuration controls how many connections may be held."
)
HTTPX_CONNECT = (
    "* The **connect** timeout specifies the maximum amount of time to wait until\n"
    "a socket connection to the requested host is established. If HTTPX is unable\n"
    "to connect within this time frame, a `ConnectTimeout` exception is raised."
)


def _source(*, content: str, rank: float, heading: str, path: str, question: str,
            terms: tuple[str, ...], anchors: tuple[str, ...] = ()) -> dict:
    matches = {
        "query-original": {
            "qualified": True,
            "mode": "and",
            "query_text": question,
            "query_terms": list(terms),
            "lexical_score": rank,
        }
    }
    query_ids = ["query-original"]
    for index, anchor in enumerate(anchors, 1):
        query_id = f"query-anchor-{index}"
        matches[query_id] = {
            "qualified": True,
            "mode": "and",
            "query_text": anchor,
            "query_terms": [anchor.casefold()],
            "exact_terms": [anchor.casefold()],
            "lexical_score": rank,
        }
        query_ids.append(query_id)
    return {
        "source_class": "project_doc",
        "path": path,
        "heading_path": heading,
        "content": content,
        "project_identity": "git:example/compact-selection",
        "authority": "source_of_truth",
        "doc_scope": "project",
        "lifecycle_status": "active",
        "freshness": "current",
        "index_freshness": "synchronized",
        "risk_flags": [],
        "line_start": 10,
        "line_end": 10 + content.count("\n"),
        "retrieval_query_ids": query_ids,
        "retrieval_query_matches": matches,
        "project_ranking": {"final_score": rank},
    }


def _retrieval(question: str, sources: list[dict], anchors: tuple[str, ...] = ()) -> dict:
    queries = [{"query_id": "query-original", "text": question, "origin": "original"}]
    for index, anchor in enumerate(anchors, 1):
        queries.append({
            "query_id": f"query-anchor-{index}",
            "text": anchor,
            "origin": "exact_anchor",
        })
    public = [item["query_id"] for item in queries]
    return {
        "question": question,
        "project_identity": "git:example/compact-selection",
        "context_pack": sources,
        "documentation_query_plan": {
            "original_question": question,
            "query_ids": public,
            "required_query_ids": ["query-original"],
            "public_query_ids": public,
            "queries": queries,
        },
    }


def _visible(payload: dict) -> str:
    return "\n\n".join(source["snippet"] for source in payload.get("sources", ()))


def test_direct_comparison_precedes_large_example():
    question = "Does a UUID string pass strict validation from JSON and from Python in the same way?"
    anchors = ("UUID", "JSON")
    terms = ("uuid", "json", "python", "strict")
    sources = [
        _source(content=UUID_DIRECT, rank=1, heading="Type coercions in strict mode",
                path="docs/concepts/strict_mode.md", question=question, terms=terms, anchors=anchors),
        _source(content=UUID_CODE, rank=10, heading="Strict mode in method calls",
                path="docs/concepts/strict_mode.md", question=question, terms=terms, anchors=anchors),
    ]
    payload, _ = project_docs_context(retrieval=_retrieval(question, sources, anchors))
    visible = _visible(payload)
    assert UUID_DIRECT in visible
    assert "```python" not in visible
    direct_only, _ = project_docs_context(retrieval=_retrieval(question, [sources[0]], anchors))
    assert docs_context_budget_tokens(payload) <= docs_context_budget_tokens(direct_only) + 40


def test_explicit_code_request_keeps_code():
    question = "Show a complete runnable code example for strict UUID validation from JSON and Python."
    anchors = ("UUID", "JSON")
    terms = ("uuid", "json", "python", "strict")
    sources = [
        _source(content=UUID_DIRECT, rank=9, heading="Type coercions in strict mode",
                path="docs/concepts/strict_mode.md", question=question, terms=terms, anchors=anchors),
        _source(content=UUID_CODE, rank=1, heading="Strict mode in method calls",
                path="docs/concepts/strict_mode.md", question=question, terms=terms, anchors=anchors),
    ]
    payload, _ = project_docs_context(retrieval=_retrieval(question, sources, anchors))
    visible = _visible(payload)
    assert "```python" in visible and "model_validate_json" in visible


def test_default_and_exception_do_not_collect_other_timeout_types():
    question = "What is HTTPX default timeout behavior: how long and which exception?"
    anchors = ("HTTPX",)
    terms = ("httpx", "timeout", "exception")
    sources = [
        _source(content=HTTPX_POOL, rank=10, heading="Fine tuning the configuration",
                path="docs/advanced/timeouts.md", question=question, terms=terms, anchors=anchors),
        _source(content=HTTPX_DEFAULT, rank=1, heading="Introduction",
                path="docs/advanced/timeouts.md", question=question, terms=terms, anchors=anchors),
        _source(content=HTTPX_CONNECT, rank=9, heading="Fine tuning the configuration",
                path="docs/advanced/timeouts.md", question=question, terms=terms, anchors=anchors),
    ]
    payload, _ = project_docs_context(retrieval=_retrieval(question, sources, anchors))
    visible = _visible(payload)
    assert "5 seconds" in visible and "TimeoutException" in visible
    assert "PoolTimeout" not in visible and "ConnectTimeout" not in visible


def test_new_required_part_beats_shortness():
    question = (
        "What is HTTPX default timeout behavior: how long and which exception, "
        "and how does connect timeout differ?"
    )
    anchors = ("HTTPX", "connect")
    base_terms = ("httpx", "timeout", "exception")
    default = _source(content=HTTPX_DEFAULT, rank=1, heading="Introduction",
                      path="docs/advanced/timeouts.md", question=question,
                      terms=base_terms, anchors=("HTTPX",))
    connect = _source(content=HTTPX_CONNECT, rank=10, heading="Fine tuning the configuration",
                      path="docs/advanced/timeouts.md", question=question,
                      terms=base_terms, anchors=anchors)
    default["retrieval_query_matches"]["query-anchor-2"] = {
        "qualified": False, "query_text": "connect", "query_terms": ["connect"],
        "exact_terms": ["connect"],
    }
    default["retrieval_query_ids"].append("query-anchor-2")
    payload, _ = project_docs_context(retrieval=_retrieval(question, [default, connect], anchors))
    visible = _visible(payload)
    assert "5 seconds" in visible and "ConnectTimeout" in visible


def test_introduction_and_signature_are_not_duplicates():
    question = "What is the signature of WidgetClient.open?"
    anchors = ("WidgetClient.open",)
    terms = ("widgetclient.open",)
    intro = "WidgetClient.open creates a client using the configured transport and returns it."
    echo = "What is the signature of WidgetClient.open?"
    signature = "`WidgetClient.open(url: str, timeout: float = 5.0) -> Response`"
    sources = [
        _source(content=intro, rank=10, heading="Introduction", path="docs/client.md",
                question=question, terms=terms, anchors=anchors),
        _source(content=echo, rank=20, heading="FAQ", path="docs/client.md",
                question=question, terms=terms, anchors=anchors),
        _source(content=signature, rank=1, heading="API", path="docs/client.md",
                question=question, terms=terms, anchors=anchors),
    ]
    payload, _ = project_docs_context(retrieval=_retrieval(question, sources, anchors))
    visible = _visible(payload)
    assert signature in visible
    assert echo not in visible
