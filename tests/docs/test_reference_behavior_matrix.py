import copy
import pytest
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


def test_forged_heading_trace_does_not_authorize_sibling(tmp_path):
    capture = capture_reference_case(tmp_path, {"Tasks.md":
        "# QueueTasks\n\nQueueTasks groups tasks.\n\n## OtherTasks\n\nTasks execute in order. Later tasks stop on error.\n"
    }, "What happens to OtherTasks when later tasks stop on error?")
    rows = capture["projection_attempts"][0]["before_projection"]["context_pack"]
    source = next(copy.deepcopy(row) for row in rows if "OtherTasks" in str(row.get("content") or ""))
    source["heading_path"] = source["section"] = "QueueTasks"
    probe = {"query_text": "When do QueueTasks stop?", "query_terms": ["tasks", "stop", "error"],
        "bound_subjects": ["queuetasks"], "bound_subject_context": "QueueTasks"}
    result = qualify_evidence(probe, query_id="query-original", evidence_text=source["content"], visible_text=source["content"], candidate=source)
    assert not result.qualified
