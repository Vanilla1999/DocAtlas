"""References are occurrences in the original question, not a word-role map."""
import pytest
from docmancer.docs.domain.query_reference_binding import query_mentions

@pytest.mark.parametrize("name", ["ARGON", "Argon", "argon", "ПАМЯТКА"])
@pytest.mark.parametrize("context,role", [("in the file", "source_locator"), ("constant", "symbol_identity"), ("library", "semantic_subject")])
def test_context_not_case_assigns_role(name, context, role):
    q = f"What is documented for {context} {name}?"
    matches = [m for m in query_mentions(q) if m.text == name]
    assert len(matches) == 1
    m = matches[0]
    assert (m.syntax_role, m.explicit) == (role, True)
    assert q[m.start:m.end] == name

def test_same_spelling_has_distinct_source_and_symbol_occurrences():
    q = "What does the constant `ARGON` mean in the file ARGON?"
    ms = [m for m in query_mentions(q) if m.text == "ARGON"]
    assert len(ms) == 2 and ms[0].mention_id != ms[1].mention_id
    assert [m.syntax_role for m in ms] == ["symbol_identity", "source_locator"]
    assert all(q[m.start:m.end] == m.text for m in ms)

@pytest.mark.parametrize("context,role", [("в файле", "source_locator"), ("из документа", "source_locator"), ("константа", "symbol_identity"), ("класс", "symbol_identity"), ("библиотека", "semantic_subject")])
def test_russian_roles_preserve_unicode_offsets(context, role):
    q = f"Как работает {context} ПАМЯТКА?"
    m = next(m for m in query_mentions(q) if m.text == "ПАМЯТКА")
    assert m.syntax_role == role and q[m.start:m.end] == "ПАМЯТКА"

@pytest.mark.parametrize("context,role", [("in the file", "source_locator"), ("constant", "symbol_identity")])
@pytest.mark.parametrize("quote", ["`", '\"'])
def test_quotes_preserve_contextual_role(context, role, quote):
    q = f"What is documented {context} {quote}ArgonGuide{quote}?"
    assert next(m for m in query_mentions(q) if m.text == "ArgonGuide").syntax_role == role

@pytest.mark.parametrize("value,role", [("Client.send", "symbol_identity"), ("docs/ArgonGuide.md", "source_locator"), (r"docs\ArgonGuide.md", "source_locator"), ("--audit-mode", "symbol_identity")])
def test_longest_span_does_not_create_substring_obligations(value, role):
    q = f"Explain {value}?"
    ms = query_mentions(q)
    m = next(m for m in ms if m.text == value)
    assert m.syntax_role == role
    assert not any(x != m and m.start <= x.start < m.end for x in ms)

def test_bare_uppercase_is_not_automatically_subject():
    ms = query_mentions("Details about SOMETHINGUNSEEN")
    assert next(m for m in ms if m.text == "SOMETHINGUNSEEN").syntax_role == "unresolved"

def test_query_and_offsets_identify_occurrence():
    a = query_mentions("file ARGON and file ARGON")
    b = query_mentions("file ARGON or file ARGON")
    assert len(a) == len(b) == 2
    assert len({m.mention_id for m in (*a, *b)}) == 4

def test_lone_quoted_filename_keeps_strict_identity():
    m = next(m for m in query_mentions("Explain `Guide.md` policy.") if m.text == "Guide.md")
    assert m.syntax_role == "symbol_identity"

def test_descriptive_nouns_do_not_invent_source_or_subject():
    for q in ("How are document headings converted into sections?", "Как документ превращается в секции?", "What does the documentation request boundary accept?"):
        assert not any(m.syntax_role in {"source_locator", "semantic_subject"} for m in query_mentions(q))

def test_slash_comparison_is_not_a_source_path():
    assert not any(m.syntax_role == "source_locator" for m in query_mentions("Explain parent/child retrieval and read/write behavior."))


def test_weak_source_hypothesis_does_not_invent_a_lowercase_exact_term():
    from docmancer.docs.domain.query_terms import query_constraint_roles
    for noun in ("project", "current", "available"):
        q = f"According to the {noun} documentation, which PermissionDecision permits BrowserPermissionGate to enter?"
        roles = query_constraint_roles(q)
        assert noun not in roles.hard_exact
        assert {"permissiondecision", "browserpermissiongate"} <= set(roles.hard_exact)
    assert "argon" in query_constraint_roles("What does the constant argon return?").hard_exact


@pytest.mark.parametrize("pronoun", ["its", "their", "our", "your", "the"])
def test_anaphoric_default_does_not_invent_a_named_subject(pronoun):
    from docmancer.docs.domain.query_terms import query_constraint_roles
    q = f"Does calling engine.Stop() imply an error, and what is {pronoun} default exit code?"
    assert pronoun not in query_constraint_roles(q).bound_subjects
    assert "engine.stop" in query_constraint_roles(q).hard_exact


def test_repeated_parse_reuses_immutable_mentions_not_scope_resolution(monkeypatch):
    from docmancer.docs.domain import query_reference_binding as binding
    original = binding.documentation_technical_anchors
    calls = []
    def tracked(text):
        calls.append(text)
        return original(text)
    monkeypatch.setattr(binding, "documentation_technical_anchors", tracked)
    q = "What command is documented in the file ColdParserCacheProbe?"
    first, second = binding.query_mentions(q), binding.query_mentions(q)
    assert first == second
    assert len(calls) == 1
    scope = binding.ScopeKey("repo:cache", "", "gen:cache")
    a = binding.resolve_references(q, scope=scope, catalog=[binding.CatalogSource("a", scope, "ColdParserCacheProbe.md", "a"*64)])
    b = binding.resolve_references(q, scope=scope, catalog=[])
    assert next(r for r in a.references if r.role == "source_locator").state == "resolved"
    assert next(r for r in b.references if r.role == "source_locator").state == "missing"


@pytest.mark.parametrize("question,value", [
    ("When converting a package, where should src/pkg be moved?", "src/pkg"),
    ("Which version line is removed from pkg/__init__.py?", "pkg/__init__.py"),
])
def test_code_paths_are_identities_not_document_locators_without_source_context(question, value):
    mention = next(m for m in query_mentions(question) if m.text == value)
    assert mention.syntax_role == "symbol_identity"
