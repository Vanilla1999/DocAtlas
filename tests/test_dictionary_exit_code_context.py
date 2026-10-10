from docmancer.docs.code_context import _module_coherence_terms, _query_terms


def test_source_navigation_does_not_expand_browser_to_a_known_product():
    assert _module_coherence_terms(["browser"]) == {"browser"}
    assert _module_coherence_terms(["tsd"]) == set()


def test_source_navigation_keeps_literal_words_without_topic_exclusions():
    assert _module_coherence_terms(["download", "files"]) == {"download", "files"}
    assert _query_terms("как работает browser", entry_symbols=None, changed_files=None) == [
        "как", "работает", "browser",
    ]


def test_explicit_source_symbols_still_have_priority_and_a_bounded_term_count():
    terms = _query_terms(" ".join(f"term{i}" for i in range(40)), entry_symbols=["entryPoint"], changed_files=["lib/source_file.py"])
    assert terms[:2] == ["entryPoint", "source_file"]
    assert len(terms) == 24
