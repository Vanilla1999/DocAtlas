"""Speedups must not change a single result.

The reference functions below are verbatim copies of the implementations they
replace (e2ca38b3); the new code is compared to them exactly.
"""
from __future__ import annotations

import random
import re
import unicodedata
from collections import Counter

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.retrieval.acquisition_reuse import acquisition_reuse_scope
from docmancer.retrieval.lexical_terms import (
    lexical_counts_utility, lexical_field_utility, lexical_terms, lexical_tokens,
)

_WORDS = re.compile(r"\w+", re.UNICODE)


def _reference_tokens(text: str) -> tuple[str, ...]:
    normalized: list[str] = []
    latin_base = False
    for character in str(text).lower():
        if "LATIN" in unicodedata.name(character, ""):
            normalized.extend(
                part for part in unicodedata.normalize("NFD", character)
                if unicodedata.category(part) != "Mn"
            )
            latin_base = True
        elif latin_base and unicodedata.category(character) == "Mn":
            continue
        else:
            normalized.append(character)
            latin_base = False
    return tuple(_WORDS.findall("".join(normalized)))


def _reference_terms(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_reference_tokens(text)))


def _reference_utility(terms, *, title, body, description, term_weights, average_body_length):
    if not terms:
        return 0.0
    body_tokens = _reference_tokens(body)
    frequencies = Counter(body_tokens)
    title_terms = frozenset(_reference_terms(title))
    description_terms = frozenset(_reference_terms(description))
    length = len(body_tokens) / max(1.0, average_body_length)
    normalization = 1.2 * (0.25 + 0.75 * length)
    weighted_content = 0.0
    for term in terms:
        frequency = frequencies[term]
        if frequency:
            weighted_content += term_weights[term] * (frequency * 2.2 / (frequency + normalization))
        elif term in title_terms:
            weighted_content += 0.5 * term_weights[term]
    content = weighted_content / sum(term_weights.values())
    routing = 0.125 * len(set(terms) & description_terms) / len(terms)
    return 1.0 + content if content else routing


_TRICKY = [
    "", "plain ascii_snake Case 42", "Если в окружении включена трассировка, флаг --trace",
    "ёжик Ёлка й Й", "Café naïve résumé Ångström", "e\u0301 x\u0301y \u0301a", "İstanbul ı I",
    "ǅ ǈ ǋ ß ẞ ø Ø æ Æ œ Œ ł Ł", "ﬁle ﬂow", "ＡＢＣ ａｂｃ", "𝐀𝐁 𝐚𝐛", "К\u0483 ш\u0301", "a\ufe0f b\u200dc",
    "Σίσυφος ΣΑΣ", "中文 テキスト 😀", "\u212a \u2126 \u1e9e", "ǰ \u0149 \u1e96", "a\u0345 \u1fbe",
    "mixed: Привет café, x\u0301; ok",
]
_POOL = (
    [chr(c) for c in range(32, 127)] + list("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАЁЙ")
    + list("éÉüÜßøØæÆłŁǅǈÅåçÇñÑœŒ") + [chr(c) for c in range(0x300, 0x370)]
    + ["\u0483", "\u05b0", "\u0e31", "\u0130", "\u0131", "Σ", "ς", "\uff21", "\uff41", "\U0001d400",
       "\ufb01", "\u200d", "\ufe0f", "\u00a0", "中", "😀", "\u1e9e", "\u212a", "\u0345", "ǰ", "\u0149"]
)


def test_lexical_tokens_fast_path_matches_reference():
    rng = random.Random(20261103)
    samples = _TRICKY + ["".join(rng.choice(_POOL) for _ in range(rng.randint(0, 40))) for _ in range(5000)]
    for text in samples:
        assert lexical_tokens(text) == _reference_tokens(text), repr(text)
        assert lexical_terms(text) == _reference_terms(text), repr(text)


def test_counts_utility_matches_field_utility_exactly():
    rng = random.Random(7)
    texts = _TRICKY + ["".join(rng.choice(_POOL) for _ in range(rng.randint(0, 80))) for _ in range(300)]
    for _ in range(2000):
        terms = _reference_terms(rng.choice(texts) + " " + rng.choice(texts))[: rng.randint(1, 12)]
        if not terms:
            continue
        weights = {term: rng.random() * 5 for term in terms}
        fields = dict(title=rng.choice(texts), body=rng.choice(texts), description=rng.choice(texts))
        average = rng.random() * 50
        expected = _reference_utility(terms, **fields, term_weights=weights, average_body_length=average)
        assert lexical_field_utility(terms, **fields, term_weights=weights, average_body_length=average) == expected
        body_tokens = lexical_tokens(fields["body"])
        restricted = Counter(token for token in body_tokens if token in set(terms))
        assert lexical_counts_utility(
            terms, body_length=len(body_tokens), body_frequencies=restricted,
            title_terms=frozenset(terms).intersection(lexical_tokens(fields["title"])),
            description_terms=frozenset(terms).intersection(lexical_tokens(fields["description"])),
            term_weights=weights, average_body_length=average,
        ) == expected


def _doc(source: str, content: str, authority: str) -> Document:
    return Document(source=source, content=content, metadata={
        "format": "markdown", "chunking_schema": "parent-child-v1",
        "child_target_tokens": 32, "child_hard_max_tokens": 64, "authority": authority,
    })


def _store(tmp_path, authorities):
    store = SQLiteStore(tmp_path / "index.db")
    store.add_documents([
        _doc(f"docs/{name}.md", f"# {name}\n\nreusetoken и в {name} alpha\n\nreusetoken beta {name}\n", authority)
        for name, authority in authorities
    ], recreate=True)
    calls: list[dict | None] = []
    original = store._query_bm25_candidates

    def counting(text, *, expand, filters):
        calls.append(filters)
        return original(text, expand=expand, filters=filters)

    store._query_bm25_candidates = counting
    return store, calls, original


def _signature(chunks):
    return [chunk.model_dump() for chunk in chunks]


def test_authority_read_reuses_pool_when_it_removes_no_window(tmp_path):
    store, calls, original = _store(tmp_path, [("a", "source_of_truth"), ("b", "source_of_truth")])
    entries: list = []
    with acquisition_reuse_scope(entries):
        first = store.acquire_candidates("reusetoken alpha", filters=None)
    with acquisition_reuse_scope(entries):
        second = store.acquire_candidates("reusetoken alpha", filters={"authority": "source_of_truth"})
    assert len(calls) == 1
    fresh = original("reusetoken alpha", expand="none", filters={"authority": "source_of_truth"})
    assert _signature(second) == _signature(first) == _signature(fresh)
    second[0].metadata["mutated"] = True
    with acquisition_reuse_scope(entries):
        third = store.acquire_candidates("reusetoken alpha", filters={"authority": "source_of_truth"})
    assert "mutated" not in third[0].metadata and _signature(third) == _signature(fresh)


def test_authority_read_searches_again_when_filter_removes_a_window(tmp_path):
    store, calls, original = _store(tmp_path, [("a", "source_of_truth"), ("b", "reference")])
    entries: list = []
    with acquisition_reuse_scope(entries):
        store.acquire_candidates("reusetoken alpha", filters=None)
        narrowed = store.acquire_candidates("reusetoken alpha", filters={"authority": "source_of_truth"})
        other_text = store.acquire_candidates("reusetoken beta", filters=None)
    assert len(calls) == 3 and other_text
    fresh = original("reusetoken alpha", expand="none", filters={"authority": "source_of_truth"})
    assert _signature(narrowed) == _signature(fresh)


def test_no_reuse_outside_a_request_scope(tmp_path):
    store, calls, _ = _store(tmp_path, [("a", "source_of_truth")])
    store.acquire_candidates("reusetoken alpha", filters=None)
    store.acquire_candidates("reusetoken alpha", filters={"authority": "source_of_truth"})
    assert len(calls) == 2


def test_request_document_structures_parse_each_body_once(monkeypatch):
    import docmancer.docs.domain.source_subject_binding as binding
    from docmancer.docs.request_memo import request_memo_scope

    parsed: list[str] = []
    original = binding.parse_markdown_parents

    def counting(raw, document_id):
        parsed.append(document_id)
        return original(raw, document_id)

    monkeypatch.setattr(binding, "parse_markdown_parents", counting)
    binding._document_structure.cache_clear()
    # More bodies than the process-wide cache holds, read cyclically as packet
    # trials do. Unscoped calls keep the existing behavior.
    documents = [(f"# Doc {n}\n\nbody {n}\n", f"doc-{n}") for n in range(40)]
    expected = [binding._document_structure(raw, doc_id) for raw, doc_id in documents]
    binding._document_structure.cache_clear()
    parsed.clear()
    with request_memo_scope():
        for _ in range(3):
            assert [binding._structure(raw, doc_id) for raw, doc_id in documents] == expected
    assert sorted(parsed) == sorted(doc_id for _, doc_id in documents)
    parsed.clear()
    for _ in range(2):
        assert [binding._structure(raw, doc_id) for raw, doc_id in documents] == expected
    assert len(parsed) == 80


def test_request_scope_parses_identical_catalog_text_once_and_rereads_the_file(tmp_path, monkeypatch):
    import docmancer.docs.project_docs_catalog as catalog_module
    from docmancer.docs.request_memo import request_memo_scope

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
    catalog = tmp_path / catalog_module.CATALOG_FILENAME

    def write(description: str) -> None:
        catalog.write_text(
            "schema_version: 1\ndocuments:\n  - path: docs/a.md\n    role: overview\n"
            f"    description: {description}\n", encoding="utf-8",
        )

    loads: list[str] = []
    original = catalog_module.yaml.load

    def counting(text, Loader):
        loads.append(text)
        return original(text, Loader=Loader)

    monkeypatch.setattr(catalog_module.yaml, "load", counting)
    write("first")
    expected = catalog_module.read_project_docs_catalog(tmp_path)
    assert expected.valid and len(loads) == 1
    with request_memo_scope():
        assert catalog_module.read_project_docs_catalog(tmp_path) == expected
        assert catalog_module.read_project_docs_catalog(tmp_path) == expected
        assert len(loads) == 2
        write("second")
        changed = catalog_module.read_project_docs_catalog(tmp_path)
        assert changed.entries[0].description == "second" and len(loads) == 3
    catalog_module.read_project_docs_catalog(tmp_path)
    assert len(loads) == 4


def test_refresh_estimate_serializes_once_with_the_same_fixed_point():
    import json
    import math
    import docmancer.docs.application.model_visible_projection as projection

    def reference(payload):
        payload["estimated_tokens"] = 0
        for _ in range(3):
            size = len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            actual = max(1, math.ceil(size / 4))
            if payload["estimated_tokens"] == actual:
                break
            payload["estimated_tokens"] = actual

    rng = random.Random(11)
    payloads = [{"padding": "x" * size} for size in range(0, 4200)]  # crosses digit-count boundaries
    payloads += [{"padding": "й" * size, "estimated_tokens": 7} for size in range(0, 900, 7)]
    for _ in range(300):
        payloads.append({
            "sources": [{"snippet": "".join(rng.choice(_POOL) for _ in range(rng.randint(0, 300))),
                         "rank": rng.random(), "n": rng.randint(-5, 10**6)} for _ in range(rng.randint(0, 6))],
            "status": rng.choice(["ok", "truncated", None]), "nested": {"estimated_tokens": rng.randint(0, 99)},
        })
    for payload in payloads:
        expected = json.loads(json.dumps(payload))
        reference(expected)
        projection._refresh_estimate(payload)
        assert payload == expected
