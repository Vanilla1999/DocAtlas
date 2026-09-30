"""Conservative, source-bound RU/EN prose profiling for this experiment only.

Not a universal language detector, a Markdown renderer, or a policy authority.
Callers supply only the already authorised snapshot (e.g. via load_sources).
Cleaned prose is NEVER substituted for canonical retrieval/evidence bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re
from typing import Mapping

from .reference_core import (
    LanguageProfile, ProseUnit, ScopeKey, aggregate_profile, classify_clean_prose, digest, hint_for,
)

EXTRACTOR_REVISION = 'markdown-prose-subset-v1-draft'
MAX_SOURCE_CHARS = 2_000_000


@dataclass(frozen=True)
class ProseSpan:
    start: int
    end: int
    raw: str
    text: str  # Measurement-only; not citable evidence.


@dataclass(frozen=True)
class ProfileBuild:
    profile: LanguageProfile
    source_hashes: tuple[tuple[str, str], ...]
    unit_count: int
    extractor_revision: str = EXTRACTOR_REVISION


def _blank(text: str) -> str:
    return ''.join(c if c in '\r\n' else ' ' for c in text)


def _clean(text: str) -> str:
    # Images and link destinations are metadata; visible link labels are prose.
    text = re.sub(r'!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])', ' ', text)
    text = re.sub(r'\[([^\]]+)\](?:\([^)]*\)|\[[^\]]*\])', r'\1', text)
    text = re.sub(r'https?://[^\s<>]+', ' ', text)
    text = re.sub(r'<[^>]*>', ' ', text)
    # Bare recognisable code identifiers: do not infer a natural language from them.
    text = re.sub(r'(?<!\w)(?:[A-Z][a-z0-9]+){2,}(?!\w)', ' ', text)
    text = re.sub(r'(?<!\w)[A-Z][A-Z0-9_]{1,}(?!\w)', ' ', text)
    text = re.sub(r'(?<!\w)[A-Za-z]\w*(?:[._][A-Za-z]\w*)+(?!\w)', ' ', text)
    text = re.sub(r'(?<!\w)--?[A-Za-z][\w-]*', ' ', text)
    text = re.sub(r'^[ \t]*(?:#{1,6}[ \t]+|[-+*>][ \t]+|\d+[.)][ \t]+)', '', text,
                  flags=re.MULTILINE)
    return re.sub(r'\s+', ' ', text.replace('*', '').replace('_', '')).strip()


def extract_prose(text: str) -> tuple[ProseSpan, ...]:
    """Extract disjoint source paragraph ranges and measurement-only prose.

    Conservatively excludes frontmatter, fenced/indented code, comments, HTML
    code/script/style, inline code and link metadata. Mixed/unsupported prose is
    left for the classifier's und bucket. Raw source character offsets survive.
    """
    if not isinstance(text, str):
        raise TypeError('source must be decoded text')
    if len(text) > MAX_SOURCE_CHARS:
        raise ValueError('source too large for this bounded experiment')
    if not text:
        return ()
    lines = text.splitlines(keepends=True)
    masked = list(lines)
    frontmatter = bool(re.fullmatch(r'\ufeff?---[ \t]*\r?\n', lines[0]))
    fence: tuple[str, int] | None = None
    for i, line in enumerate(lines):
        if frontmatter:
            masked[i] = _blank(line)
            if i and re.fullmatch(r'(?:---|\.\.\.)[ \t]*(?:\r?\n)?', line):
                frontmatter = False
            continue
        # Accommodate code fences in lists/quotes without treating their code as prose.
        logical = re.sub(r'^\s*(?:>\s*)+', '', line)
        logical = re.sub(r'^\s*(?:[-+*]|\d+[.)])\s+', '', logical)
        marker = re.match(r'^\s*(`{3,}|~{3,})([^\r\n]*)', logical)
        if fence is not None:
            masked[i] = _blank(line)
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1]
                    and not marker[2].strip()):
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            masked[i] = _blank(line)
        elif (line.startswith(('    ', '\t'))
              or re.match(r'^ {0,3}\[[^\]]+\]:', line)):
            masked[i] = _blank(line)
    working = ''.join(masked)
    # Blanking, rather than deleting, preserves original range coordinates.
    for pattern in (r'<!--[\s\S]*?(?:-->|\Z)',
                    r'<(pre|code|script|style)\b[^>]*>[\s\S]*?(?:</\1\s*>|\Z)',
                    r'(`+)[\s\S]*?\1'):
        working = re.sub(pattern, lambda m: _blank(m[0]), working, flags=re.IGNORECASE)
    spans: list[ProseSpan] = []
    start: int | None = None
    end = 0
    cursor = 0

    def flush() -> None:
        nonlocal start
        if start is not None:
            clean = _clean(working[start:end])
            if any(c.isalpha() for c in clean):
                spans.append(ProseSpan(start, end, text[start:end], clean))
        start = None

    for line in working.splitlines(keepends=True):
        if line.strip():
            if start is None:
                start = cursor
            end = cursor + len(line)
        else:
            flush()
        cursor += len(line)
    flush()
    return tuple(spans)


def catalog_digest(documents: Mapping[str, str]) -> str:
    """Same canonical source-set digest used by baseline_probe.load_sources."""
    entries = []
    for path, text in documents.items():
        if not isinstance(path, str) or not path or '\\' in path:
            raise ValueError('invalid source path')
        rel = PurePosixPath(path)
        if (rel.is_absolute() or '..' in rel.parts or rel.as_posix() != path
                or rel.suffix != '.md' or not isinstance(text, str)):
            raise ValueError('invalid source path or text')
        if len(text) > MAX_SOURCE_CHARS:
            raise ValueError('source too large for this bounded experiment')
        entries.append((path, digest(text)))
    return digest(json.dumps(sorted(entries), ensure_ascii=False, separators=(',', ':')))


def profile_sources(documents: Mapping[str, str], key: ScopeKey) -> ProfileBuild:
    """Aggregate original source paragraphs once, never repeated retrieval chunks.

    The key must be issued by the scope resolver; this helper cannot decide ACLs,
    source freshness or which library a user meant. A catalog mismatch is fatal.
    """
    if catalog_digest(documents) != key.catalog_sha256:
        raise ValueError('source catalog does not match the scope snapshot')
    units = []
    hashes = []
    for path, text in sorted(documents.items()):
        source_hash = digest(text)
        hashes.append((path, source_hash))
        for span in extract_prose(text):
            identity = digest(json.dumps((path, source_hash, span.start, span.end)))
            units.append(ProseUnit(identity, classify_clean_prose(span.text),
                                   sum(c.isalpha() for c in span.text)))
    return ProfileBuild(aggregate_profile(key, units), tuple(hashes), len(units))


def profile_hint(build: ProfileBuild, current: ScopeKey) -> dict | None:
    """Invalidate the hint after an extraction-method change as well as snapshot changes."""
    if build.extractor_revision != EXTRACTOR_REVISION:
        return None
    hint = hint_for(build.profile, current)
    if hint is not None:
        hint['extraction_method'] = build.extractor_revision
    return hint
