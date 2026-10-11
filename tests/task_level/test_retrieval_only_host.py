"""Host compatibility with the actual retrieval-only public projection."""
from copy import deepcopy

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import _refresh_estimate
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from eval.task_level.one_call_agent_loop import FakeLoopAdapter, LoopCapabilities, OneCallAgentLoop, validate_docatlas_result
from docmancer.docs.interfaces.host_context import (
    EvidenceDeliveryError, SourceReadController, extract_tool_payload,
)


@pytest.fixture
def context():
    query = "job status terminal"
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": [{
            "source_class": "project_doc", "path": "docs/jobs.md",
            "heading_path": "Polling", "content": "Poll the job until its status is terminal.",
            "project_identity": "git:example/project", "authority": "source_of_truth",
            "doc_scope": "project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "retrieval_query_ids": ["query-original"],
            "retrieval_query_matches": {"query-original": {
                "qualified": True, "mode": "and", "query_text": query,
            }},
        }],
        "documentation_query_plan": build_documentation_query_plan(query).as_payload(),
    })
    assert payload["kind"] == "docs_context"
    assert payload["context_available"] is True
    assert payload["sources"]
    assert payload["answer_policy"] == "cite_only"
    assert all(payload[key] is False for key in ("answer_supported", "answer_available", "edit_ready"))
    for source in payload["sources"]:
        entry = snapshot[source["evidence_id"]]
        assert entry["projected_source"] == source
        assert entry["source"]["retrieval_query_matches"]["query-original"]["qualified"] is True
    assert not validate_docatlas_result(payload)
    return payload












def controller_fixture(context, callback):
    source = context['sources'][0]
    source.update(source_uri='docatlas://source/' + 'a' * 24, line_end=2)
    return SourceReadController(context, requested_facts={'polling': 'When does polling stop?'}, read_resource=callback)














def _registered_range_context(context):
    value = deepcopy(context)
    source = value['sources'][0]
    source.update(line_start=162, line_end=168)
    uri = 'docatlas://source/' + 'b' * 24
    value['read_next'] = [{
        'source_uri': uri,
        'path': source['path_or_url'],
        'project_identity': source['project_identity'],
        'snapshot_sha256': 'sha256:' + 'f' * 64,
        'line_start': 156,
        'line_end': 172,
        'reason': 'inspect_source_context',
    }]
    _refresh_estimate(value)
    return value, uri


def _registered_range_result(context, *, start=156, end=172, continuation=None):
    source = context['sources'][0]
    return dict(
        status='truncated' if continuation else 'complete',
        path=source['path_or_url'], project_identity=source['project_identity'],
        content_sha256='sha256:' + 'f' * 64,
        line_start=start, line_end=end,
        snippet='\n'.join(f'Range line {line}.' for line in range(start, end + 1)),
        continuation=continuation,
    )











