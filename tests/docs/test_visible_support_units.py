from __future__ import annotations


def _native_source(tmp_path, text: str, question: str):
    from tests.docs._reference_binding_fixtures import capture_reference_case

    cap = capture_reference_case(tmp_path, {"Guide.md": text}, question)
    source = dict(cap["projection_attempts"][0]["before_projection"]["context_pack"][0])
    plan = cap["projection_attempts"][0]["before_projection"]["documentation_query_plan"]
    source["_independent_query_plan"] = plan
    source["_qualification_candidate"] = dict(source)
    source["_expected_project_identity"] = source["project_identity"]
    source["_lifecycle_intent"] = "current"
    source["path_or_url"] = source["path"]
    query_text = {
        str(item.get("query_id") or ""): str(item.get("text") or "")
        for item in plan.get("queries") or ()
        if isinstance(item, dict)
    }
    return source, query_text
