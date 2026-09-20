"""Native-only reference fixtures; no replacement qualification or result stubs."""
from tests.docs._global_evidence_fixtures import capture_fixture, visible
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection


def capture_reference_case(tmp_path, docs, question, *, lookups=()):
    capture = capture_fixture(tmp_path, docs, question, lookups)
    payload = capture["public_payload"]
    if payload.get("kind") == "docs_context":
        attempts = capture.get("projection_attempts") or []
        assert attempts
        assert validate_model_visible_projection(payload, snapshot=attempts[-1]["snapshot"], max_tokens=800) == []
    for row in payload.get("sources") or []:
        assert row["path_or_url"] in docs
    return capture
