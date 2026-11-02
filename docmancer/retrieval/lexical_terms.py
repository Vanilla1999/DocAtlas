"""Shared literal terms and field separation for lexical retrieval.

Queries remain the caller's words: no stemming, translations, synonyms, or
language-specific omission lists. Underscores remain part of a literal source
word: metadata's source_of_truth cannot make a body's "of" a content match.
FTS supplies a candidate superset; these source-word checks are deliberately
stricter than its tokenizer. Latin accents are normalized without folding
distinct Cyrillic letters such as е and ё.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import PurePosixPath
from typing import Iterable, Mapping

from docmancer.docs.domain.query_reference_binding import (
    normalize_reference_path, query_mentions,
)


_WORDS = re.compile(r"\w+", re.UNICODE)


def lexical_tokens(text: str) -> tuple[str, ...]:
    """Return normalized words, including occurrences needed for scoring."""
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
            # The decomposed spelling of the same Latin word is equivalent.
            continue
        else:
            normalized.append(character)
            latin_base = False
    return tuple(_WORDS.findall("".join(normalized)))


def lexical_terms(text: str) -> tuple[str, ...]:
    """Return distinct normalized words in their original occurrence order."""
    return tuple(dict.fromkeys(lexical_tokens(text)))


def query_terms(text: str) -> tuple[str, ...]:
    """Use the same literal terms for retrieval and merged evidence selection."""
    return lexical_terms(text)


def explicit_source_locators(query: str) -> tuple[str, ...]:
    """Keep complete literal filenames/paths separate from content words.

    The existing occurrence parser supplies the literal spellings. A qualified
    technical spelling can name a stored file (including YAML), but a simple
    word, absolute machine path, URL or traversal can never open this route.
    Matching a locator is only candidate routing, never source authorization.
    """
    locators = []
    for mention in query_mentions(query):
        value = normalize_reference_path(mention.text)
        if (not mention.explicit or mention.syntax_role not in {"source_locator", "symbol_identity"}
                or not value or value.startswith(("/", "~/")) or ":" in value
                or any(part in {"", ".", ".."} for part in value.split("/"))
                or not PurePosixPath(value).suffix):
            continue
        locators.append(value)
    return tuple(dict.fromkeys(locators))


def resolve_source_locators(
    locators: tuple[str, ...], sources: Iterable[tuple[str, str]],
) -> dict[str, tuple[str, ...]]:
    """Resolve whole paths or unique basenames in the complete allowed pool.

    Callers supply already filtered source identities, before candidate LIMIT.
    Exact spelling precedes case-insensitive matching, as in the source
    reference resolver. A supplied relative directory is never discarded to
    rescue an unknown path through a coincidentally matching basename.
    """
    paths = [(identity, normalize_reference_path(path)) for identity, path in sources]
    resolved: dict[str, list[str]] = {}
    for locator in locators:
        tiers = [paths]
        if "/" not in locator:
            tiers.append([(identity, PurePosixPath(path).name) for identity, path in paths])
        matches: set[str] = set()
        for folded in (False, True):
            for tier in tiers:
                matches = {identity for identity, path in tier
                           if (path.casefold() == locator.casefold() if folded else path == locator)}
                if matches:
                    break
            if matches:
                break
        if len(matches) == 1:
            resolved.setdefault(next(iter(matches)), []).append(locator)
    return {identity: tuple(values) for identity, values in resolved.items()}


def lexical_field_matches(
    terms: tuple[str, ...], *, title: str, body: str, description: str = "",
) -> dict[str, tuple[str, ...]]:
    """Keep source words separate from catalog routing descriptions."""
    matches: dict[str, tuple[str, ...]] = {}
    for name, value in (("title", title), ("body", body), ("description", description)):
        words = frozenset(lexical_terms(value))
        matches[name] = tuple(term for term in terms if term in words)
    return matches


def lexical_field_utility(
    terms: tuple[str, ...], *, title: str, body: str, description: str,
    term_weights: Mapping[str, float], average_body_length: float,
) -> float:
    """Rank source matches before weaker, explicitly routing-only matches.

    Body terms use BM25's saturating frequency and length normalization (k1=1.2,
    b=0.75), with IDF supplied from clean matching source windows. A heading adds
    half-weight credit only for words absent from the body. Catalog descriptions
    can retrieve a routing-only row at at most one eighth of a point, outside
    the source statistics. They never boost a source score: a complete catalog
    description cannot make a weak body match outrank a specific body match.
    This acquisition utility does not claim factual support.
    """
    if not terms:
        return 0.0
    body_tokens = lexical_tokens(body)
    frequencies = Counter(body_tokens)
    title_terms = frozenset(lexical_terms(title))
    description_terms = frozenset(lexical_terms(description))
    length = len(body_tokens) / max(1.0, average_body_length)
    normalization = 1.2 * (0.25 + 0.75 * length)
    weighted_content = 0.0
    for term in terms:
        frequency = frequencies[term]
        if frequency:
            weighted_content += term_weights[term] * (
                frequency * 2.2 / (frequency + normalization)
            )
        elif term in title_terms:
            weighted_content += 0.5 * term_weights[term]
    content = weighted_content / sum(term_weights.values())
    routing = 0.125 * len(set(terms) & description_terms) / len(terms)
    return 1.0 + content if content else routing
