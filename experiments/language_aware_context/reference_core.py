"""Executable design examples, NOT a DocAtlas integration or a retrieval engine.

Inputs must be obtained by an adapter from verified, allowed snapshots. The
prose classifier is deliberately conservative and is only a routing hint.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable, Iterable, Literal

Language = Literal['en', 'ru', 'und']
DETECTOR_REVISION = 'ru-en-prose-hint-v1-draft'
LANGUAGES = ('en', 'ru', 'und')


def digest(text: str) -> str:
    return sha256(text.encode('utf-8')).hexdigest()


def _hash(value: str) -> None:
    if not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('expected a SHA-256 digest')


@dataclass(frozen=True)
class ScopeKey:
    # These fields come from the resolver, never from language inference.
    scope_id: str
    version: str
    generation_id: str
    catalog_sha256: str

    def __post_init__(self) -> None:
        if not all((self.scope_id, self.version, self.generation_id)):
            raise ValueError('incomplete scope binding')
        _hash(self.catalog_sha256)


@dataclass(frozen=True)
class ProseUnit:
    # Non-overlapping source ranges after prose extraction, not index overlaps.
    unit_id: str
    language: Language
    letter_count: int

    def __post_init__(self) -> None:
        if not self.unit_id or self.language not in LANGUAGES:
            raise ValueError('invalid prose unit')
        if type(self.letter_count) is not int or self.letter_count < 0:
            raise ValueError('invalid prose mass')


EN_HINT_WORDS = frozenset('the this that these those with without when which '
    'before after should must will does not only for from are is and or'.split())
RU_HINT_WORDS = frozenset('это этот эта эти для когда который которая которые '
    'перед после должен должна должны можно нельзя только если при без '
    'что как или между чтобы будет уже'.split())


def classify_clean_prose(text: str) -> Language:
    """Clean prose ONLY. Does not parse Markdown and does not detect all languages.

    All mixed/short/ambiguous blocks may be und. Three distinct hint words and
    >=95% of alphabetic characters in one supported alphabet are draft rules;
    their accuracy must be measured on separately labelled prose.
    """
    letters = [c for c in text.casefold() if c.isalpha()]
    if len(letters) < 24:
        return 'und'
    words = set(re.findall(r'[^\W\d_]+', text.casefold()))
    latin = sum('a' <= c <= 'z' for c in letters)
    cyrillic = sum('а' <= c <= 'я' or c == 'ё' for c in letters)
    # Distinctive non-Russian Cyrillic letters must not be re-labelled Russian.
    if any(c in text.casefold() for c in 'іїєґў'):
        return 'und'
    if latin / len(letters) >= .95 and len(words & EN_HINT_WORDS) >= 3:
        return 'en'
    if cyrillic / len(letters) >= .95 and len(words & RU_HINT_WORDS) >= 3:
        return 'ru'
    return 'und'


@dataclass(frozen=True)
class LanguageProfile:
    key: ScopeKey
    counts: tuple[int, int, int]  # en, ru, und; one denominator
    detector_revision: str = DETECTOR_REVISION

    def __post_init__(self) -> None:
        if len(self.counts) != 3 or any(type(n) is not int or n < 0 for n in self.counts):
            raise ValueError('invalid language counts')


def aggregate_profile(key: ScopeKey, units: Iterable[ProseUnit]) -> LanguageProfile:
    counts: Counter[str] = Counter()
    seen: dict[str, ProseUnit] = {}
    for unit in units:
        previous = seen.get(unit.unit_id)
        if previous is not None:
            if previous != unit:
                raise ValueError('conflicting duplicate prose unit')
            continue
        seen[unit.unit_id] = unit
        counts[unit.language] += unit.letter_count
    return LanguageProfile(key, tuple(counts[x] for x in LANGUAGES))


def hint_for(profile: LanguageProfile, current: ScopeKey) -> dict | None:
    """Mismatched or empty profiles yield no hint, not a guessed language."""
    if profile.key != current or profile.detector_revision != DETECTOR_REVISION:
        return None
    total = sum(profile.counts)
    if not total or not sum(profile.counts[:2]):
        return None
    shares = dict(zip(LANGUAGES, (n / total for n in profile.counts)))
    present = [x for x in ('en', 'ru') if shares[x] > 0]
    present.sort(key=lambda x: (-shares[x], x))
    return {
        'scope_id': current.scope_id,
        'version': current.version,
        'generation_id': current.generation_id,
        'catalog_sha256': current.catalog_sha256,
        'method': profile.detector_revision,
        'basis': 'classified_prose_letters',
        'shares': shares,
        'query_languages': present,  # Never a document-language filter.
        'hint_only': True,
    }


def make_request(question: str, lookups: Iterable[str], *, project_path: str,
                 scope: str = 'project', module_path: str | None = None) -> dict:
    """Draft stricter experiment profile: <=3 lookups, <=240 chars each.

    This is not semantic validation. Gold leakage, negation and intent require
    independent review. No source/version/authority field is accepted from a host.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError('missing original question')
    if isinstance(lookups, (str, bytes)):
        raise ValueError('lookups must be a collection')
    queries = tuple(lookups)
    if len(queries) > 3 or any(not isinstance(q, str) or not q.strip()
                              or len(q) > 240 for q in queries):
        raise ValueError('invalid lookup budget')
    if len(set(queries)) != len(queries) or question in queries:
        raise ValueError('duplicate lookup')
    if scope not in ('project', 'module', 'all') or not project_path:
        raise ValueError('invalid scope')
    if (scope == 'module') != bool(module_path):
        raise ValueError('module scope requires exactly one module path')
    result = {'question': question, 'project_path': project_path, 'scope': scope}
    if queries:
        result['lookup_queries'] = list(queries)
    if module_path:
        result['module_path'] = module_path
    return result


@dataclass(frozen=True)
class LiteralSpan:
    start: int
    end: int


def mask_literals(question: str, spans: Iterable[LiteralSpan]) -> tuple[str, tuple[str, ...]]:
    """Spans are authoritative original-query character offsets from the parser."""
    if '[[LIT_' in question:
        raise ValueError('placeholder collision')
    spans = tuple(sorted(spans, key=lambda s: s.start))
    cursor, parts, literals = 0, [], []
    for i, span in enumerate(spans):
        if (type(span.start) is not int or type(span.end) is not int
                or not cursor <= span.start < span.end <= len(question)):
            raise ValueError('invalid or overlapping literal span')
        parts += [question[cursor:span.start], f'[[LIT_{i}]]']
        literals.append(question[span.start:span.end])
        cursor = span.end
    parts.append(question[cursor:])
    return ''.join(parts), tuple(literals)


def restore_lookups(lookups: Iterable[str], literals: tuple[str, ...]) -> tuple[str, ...]:
    queries = tuple(lookups)
    expected = {f'[[LIT_{i}]]' for i in range(len(literals))}
    present = set(re.findall(r'\[\[LIT_[^\]]*\]\]', '\n'.join(queries)))
    if present != expected:
        raise ValueError('missing or invented protected literal')
    def replace(match: re.Match[str]) -> str:
        return literals[int(match[1])]
    result = tuple(re.sub(r'\[\[LIT_(\d+)\]\]', replace, q) for q in queries)
    if any('[[LIT_' in q for q in result):
        raise ValueError('malformed protected literal')
    return result


@dataclass(frozen=True)
class SourceSpan:
    key: ScopeKey
    source_id: str
    parent_id: str
    snapshot_sha256: str
    ordinal: int
    char_start: int
    char_end: int
    text: str


def adjacent_window(seed: SourceSpan, neighbor: SourceSpan, *, source_text: str,
                    source_policy_allows: Callable[[SourceSpan], bool]) -> SourceSpan | None:
    """Propose exact contiguous bytes; NEVER qualify evidence or assign coverage.

    Caller must have an actually qualified seed, then run real reference/exact/
    witness checks and the actual DTO budget after materializing this proposal.
    A mock callback in a unit test is NOT a source-policy integration test.
    """
    if (seed.key, seed.source_id, seed.parent_id, seed.snapshot_sha256) != (
        neighbor.key, neighbor.source_id, neighbor.parent_id, neighbor.snapshot_sha256
    ):
        return None
    if abs(seed.ordinal - neighbor.ordinal) != 1:
        return None
    if not seed.parent_id or digest(source_text) != seed.snapshot_sha256:
        return None
    for span in (seed, neighbor):
        if not (type(span.char_start) is int and type(span.char_end) is int
                and 0 <= span.char_start < span.char_end <= len(source_text)
                and source_text[span.char_start:span.char_end] == span.text):
            return None
        if source_policy_allows(span) is not True:
            return None
    first, second = sorted((seed, neighbor), key=lambda s: s.char_start)
    if first.char_end > second.char_start:
        return None
    if source_text[first.char_end:second.char_start].strip():
        return None  # Do not jump across omitted text, even in the same parent.
    proposal = SourceSpan(seed.key, seed.source_id, seed.parent_id,
        seed.snapshot_sha256, first.ordinal, first.char_start, second.char_end,
        source_text[first.char_start:second.char_end])
    if source_policy_allows(proposal) is not True:
        return None  # The combined window can expose new risks too.
    return proposal
