from importlib import import_module




def test_capture_public_call_records_full_serializable_projection_trace(tmp_path, request):
    import json
    from eval.project_context_quality.capture_public_context import capture_public_call
    from tests.docs.test_docs_context_read_next import _real_service

    service = _real_service(tmp_path, request)
    request = {
        "question": "How does docs_status polling progress work?",
        "lookup_queries": ["docs_status polling progress"],
        "project_path": str(tmp_path),
        "scope": "all",
    }
    record = capture_public_call(service, request)
    assert record["request"] == request
    assert record["public_payload"]["kind"] == "docs_context"
    assert record["public_payload"]["sources"]
    assert len(record["projection_attempts"]) == 1
    attempt = record["projection_attempts"][0]
    assert attempt["before_projection"]["context_pack"]
    assert attempt["projected_payload"]["sources"]
    assert isinstance(attempt["snapshot"], dict)
    json.dumps(record, ensure_ascii=False, sort_keys=True)




def test_capture_observer_does_not_change_public_evidence(tmp_path, request):
    fixture_request = request
    from copy import deepcopy
    from eval.project_context_quality.capture_public_context import capture_public_call
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from tests.docs.test_docs_context_read_next import _real_service

    request = {
        "question": "How does docs_status polling progress work?",
        "lookup_queries": ["docs_status polling progress"],
        "scope": "all",
    }
    plain_root = tmp_path / "plain"
    observed_root = tmp_path / "observed"
    plain_service = _real_service(plain_root, fixture_request)
    observed_service = _real_service(observed_root, fixture_request)

    plain = call_docs_tool_payload(
        "get_docs_context", {**deepcopy(request), "project_path": str(plain_root)}, plain_service,
    )
    captured = capture_public_call(
        observed_service, {**deepcopy(request), "project_path": str(observed_root)},
    )["public_payload"]

    def stable(payload):
        value = deepcopy(payload)
        for row in value.get("read_next") or ():
            row.pop("source_uri", None)
            row["project_identity"] = "<project>"
        for row in value.get("sources") or ():
            row["project_identity"] = "<project>"
        return value

    left, right = stable(plain), stable(captured)
    for value in (left, right):
        for row in value.get("sources") or ():
            row["path_or_url"] = row["path_or_url"].replace(str(plain_root), "<root>").replace(str(observed_root), "<root>")
        for row in value.get("read_next") or ():
            row["path"] = row["path"].replace(str(plain_root), "<root>").replace(str(observed_root), "<root>")
    assert [row["snippet"] for row in left["sources"]] == [row["snippet"] for row in right["sources"]]
    assert left["context_quality"] == right["context_quality"]
    assert left["kind"] == right["kind"] == "docs_context"
