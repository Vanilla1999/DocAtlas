"""Meaning-level checks shared by the host scope contract tests."""
import re


def assert_public_scope_guidance(tool):
    """Accept compact/expanded prose while keeping every scope boundary explicit.

    Behavioral isolation and literal host examples live in test_host_scope_contract;
    this helper checks that the advertised guidance explains those same boundaries.
    """
    properties = tool["inputSchema"]["properties"]
    scope = properties["scope"]
    clauses = dict(re.findall(r"\b(project|module|all)\s*=\s*([^;]+)", scope["description"]))
    assert set(clauses) == {"project", "module", "all"}
    assert "repo-level docs only" in clauses["project"]
    assert "one module" in clauses["module"]
    assert re.search(r"repo(?:-level)?\s*(?:\+|plus)\s*modules\b", clauses["all"])
    assert "same repository" in clauses["all"]
    assert "without module filters" in clauses["all"]
    assert "always implies module scope" in properties["module_path"]["description"]
    assert "Preserve explicit project/library/version/scope/path" in tool["description"]
    assert re.search(r"never widen scope from (?:question wording|prose)\b", tool["description"], re.I)
    assert "default" not in scope
    assert scope["type"] == ["string", "null"]
    assert scope["enum"] == ["project", "module", "all", None]
