import pytest

from docmancer.docs.interfaces.mcp.context_intents import (
    InvalidContextIntent,
    normalize_context_intents,
)


@pytest.mark.parametrize("mode,project_only", [
    (None, True), ("auto", True), ("project", True),
    ("dependency", False), ("mixed", False), ("library", False),
])
def test_implicit_intents_follow_route(mode, project_only):
    args = {"project_path": "/repo"}
    if mode is not None:
        args["mode"] = mode
    request, lifecycle, implicit, mutation = normalize_context_intents(args, "Read docs")
    assert request == "read"
    assert lifecycle == ("current" if project_only else None)
    assert implicit is project_only
    assert mutation.operation == "none"


@pytest.mark.parametrize("mode", ["dependency", "mixed", "library"])
@pytest.mark.parametrize("intent", [
    {"request_intent": "read"}, {"lifecycle_intent": "current"},
])
def test_explicit_project_intents_rejected_for_other_routes(mode, intent):
    with pytest.raises(InvalidContextIntent):
        normalize_context_intents({"project_path": "/repo", "mode": mode, **intent}, "Read docs")


@pytest.mark.parametrize("libraries", [{"library": "lib"}, {"libraries": ["lib"]}])
def test_auto_with_library_has_no_project_defaults(libraries):
    _, lifecycle, implicit, _ = normalize_context_intents({"project_path": "/repo", **libraries}, "Read docs")
    assert lifecycle is None
    assert implicit is False


def test_explicit_project_lifecycle_preserved():
    request, lifecycle, implicit, _ = normalize_context_intents(
        {"project_path": "/repo", "mode": "project", "lifecycle_intent": "historical"}, "Read docs",
    )
    assert (request, lifecycle, implicit) == ("read", "historical", True)
