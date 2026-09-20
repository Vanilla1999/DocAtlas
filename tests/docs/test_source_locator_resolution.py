"""Complete scoped catalog linking; no filename whitelist or top-k winner."""
from dataclasses import replace
import pytest
from docmancer.docs.domain.query_reference_binding import ScopeKey, CatalogSource, resolve_references

SCOPE = ScopeKey("repo:test", "v2", "snapshot:2")
def source(path, identity, scope=SCOPE):
    return CatalogSource(identity, scope, path, "a" * 64)
def resolve(name, catalog, **kwargs):
    return resolve_references(f"What command is documented in the file {name}?", catalog=catalog, scope=SCOPE, **kwargs)
def locator(plan):
    return next(r for r in plan.references if r.role == "source_locator")

@pytest.mark.parametrize("name", ["VeloraGuide", "VELORAGUIDE", "veloraguide", "ПАМЯТКА"])
def test_arbitrary_stem_resolves(name):
    r = locator(resolve(name, [source("docs/"+name+".md", "doc:1")]))
    assert r.state == "resolved" and r.source_ids == ("doc:1",)

def test_missing_explicit_source_is_not_softened():
    r = locator(resolve("MissingGuide", [source("Other.md", "doc:1")]))
    assert r.state == "missing" and not r.source_ids

def test_duplicate_basename_is_ambiguous():
    r = locator(resolve("VeloraGuide", [source("a/VeloraGuide.md", "a"), source("b/VeloraGuide.md", "b")]))
    assert r.state == "ambiguous" and r.source_ids == ("a", "b")

def test_path_disambiguates_and_does_not_fall_back_to_basename():
    rows = [source("a/VeloraGuide.md", "a"), source("b/VeloraGuide.md", "b")]
    assert locator(resolve("a/VeloraGuide.md", rows)).source_ids == ("a",)
    assert locator(resolve("c/VeloraGuide.md", rows)).state == "missing"

@pytest.mark.parametrize("scope", [replace(SCOPE, project_id="other"), replace(SCOPE, version="v1"), replace(SCOPE, snapshot_id="snapshot:1")])
def test_scope_is_applied_before_matching(scope):
    assert locator(resolve("VeloraGuide", [source("VeloraGuide.md", "old", scope)])).state == "missing"

@pytest.mark.parametrize("name,state,ids", [("Foo.md", "resolved", ("upper",)), ("foo.md", "resolved", ("lower",)), ("FOO", "ambiguous", ("lower", "upper"))])
def test_exact_case_precedes_casefold_collisions(name, state, ids):
    r = locator(resolve(name, [source("Foo.md", "upper"), source("foo.md", "lower")]))
    assert (r.state, r.source_ids) == (state, ids)

def test_unique_casefold_alias_resolves():
    assert locator(resolve("VELORAGUIDE", [source("VeloraGuide.md", "d")])).source_ids == ("d",)

def test_truncated_catalog_cannot_prove_unique_or_missing():
    for rows in ([], [source("VeloraGuide.md", "d")]):
        r = locator(resolve("VeloraGuide", rows, catalog_complete=False))
        assert r.state == "unresolved" and not r.source_ids

def test_equal_hash_does_not_merge_sources_and_order_is_irrelevant():
    rows = [source("a/Guide.md", "a"), source("b/Guide.md", "b")]
    assert resolve("Guide", rows) == resolve("Guide", rows[::-1])
    assert len(locator(resolve("Guide", rows)).source_ids) == 2

@pytest.mark.parametrize("name", ["../Guide.md", "/Guide.md", "a/../Guide.md", "C:/Guide.md"])
def test_root_or_traversal_is_not_silently_rebased(name):
    assert locator(resolve(name, [source("Guide.md", "d")])).state == "missing"

def test_separator_normalization_does_not_change_identity():
    assert locator(resolve(r"docs\Guide.md", [source("docs/Guide.md", "d")])).source_ids == ("d",)

def test_unknown_suffix_is_not_an_alias():
    assert locator(resolve("Guide", [source("Guide.exe", "d")])).state == "missing"

def test_known_suffixes_share_catalog_contract():
    from docmancer.docs.project_docs_catalog import SUPPORTED_EXTENSIONS
    for suffix in SUPPORTED_EXTENSIONS:
        assert locator(resolve("Guide", [source("Guide"+suffix, "d")])).source_ids == ("d",)

def test_implicit_in_the_document_needs_catalog_evidence():
    q = "What three capabilities summarize Lumina in the VeloraGuide?"
    p = resolve_references(q, catalog=[source("VeloraGuide.md", "d")], scope=SCOPE)
    assert locator(p).source_ids == ("d",)
    empty = resolve_references(q, catalog=[], scope=SCOPE)
    assert not any(r.role == "source_locator" for r in empty.references)

def test_library_context_wins_over_coincidental_filename():
    p = resolve_references("How does the library ARGON handle requests?", catalog=[source("ARGON.md", "d")], scope=SCOPE)
    assert not any(r.role == "source_locator" for r in p.references)
    assert any(r.role == "semantic_subject" and r.mention.text == "ARGON" for r in p.references)

def test_bare_in_library_does_not_prove_document_role():
    p = resolve_references("How are requests handled in HTTPX?", catalog=[source("HTTPX.md", "d")], scope=SCOPE)
    assert not any(r.role == "source_locator" for r in p.references)

def test_symbol_and_source_keep_independent_obligations():
    p = resolve_references("What does the constant `ARGON` mean in the file ARGON?", catalog=[source("ARGON.md", "d")], scope=SCOPE)
    assert [(r.role, r.source_ids) for r in p.references] == [("symbol_identity", ()), ("source_locator", ("d",))]

def test_unversioned_project_still_needs_a_real_snapshot():
    scope = replace(SCOPE, version="")
    p = resolve_references("Read the file Guide", catalog=[source("Guide.md", "d", scope)], scope=scope)
    assert locator(p).state == "resolved"
    missing = replace(scope, snapshot_id="")
    p = resolve_references("Read the file Guide", catalog=[source("Guide.md", "d", missing)], scope=missing)
    assert locator(p).state == "unresolved"
