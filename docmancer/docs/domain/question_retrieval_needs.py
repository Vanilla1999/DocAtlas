"""Original-question literal retrieval needs, never semantic interpretation."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from docmancer.docs.domain.query_reference_binding import QueryMention, query_mentions


@dataclass(frozen=True, slots=True)
class RetrievalNeed:
    need_id: str
    query_span_start: int
    query_span_end: int
    query_span_text: str
    subject: str
    relation: str
    context: str
    hard_exact: tuple[str, ...]


def _literal_symbol_mentions(question: str) -> tuple[QueryMention, ...]:
    """Body identities only; source paths belong to reference qualification.

    Preserve occurrences so a locator and a separately written symbol with the
    same spelling cannot erase each other's obligations. Path-shaped literals
    are not subjects, even when the reference extractor labels them symbols.
    """
    return tuple(mention for mention in query_mentions(question)
                 if mention.explicit and mention.syntax_role == "symbol_identity"
                 and not any(separator in mention.text for separator in ("/", "\\")))


def retrieval_needs(question: str) -> tuple[RetrievalNeed, ...]:
    """Keep one unresolved full-original need for every nonblank question."""
    return _cached_retrieval_needs(str(question or ""))


def _need_subject(text: str) -> str:
    """Compatibility hook: literal needs never nominate a semantic subject."""
    return ""


@lru_cache(maxsize=256)
def _cached_retrieval_needs(raw: str) -> tuple[RetrievalNeed, ...]:
    # Immutable literal syntax only. Source identities/approvals are checked by
    # the current-source qualifier, never inferred or cached here.
    if not raw.strip():
        return ()
    exact = tuple(dict.fromkeys(mention.text.casefold()
                               for mention in _literal_symbol_mentions(raw)))
    return (RetrievalNeed("need-1", 0, len(raw), raw, "", "unresolved", "", exact),)


__all__ = ["RetrievalNeed", "retrieval_needs"]
