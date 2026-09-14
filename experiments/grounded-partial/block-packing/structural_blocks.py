"""Whole-source-block alternatives, experiment only; no gold or new retrieval.

Only the fragment producer and final expansion are replaced. The existing
qualifier, ranking, novelty, source policy and full DTO budget remain in charge.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import re
from typing import Any
from unittest.mock import patch

from markdown_it import MarkdownIt
from docmancer.docs.application import docs_context_projection as projection

# Work limits, not text-length truncation. Exceeding them aborts the experiment.
MAX_DOCUMENT_BLOCKS = 4096
MAX_CANDIDATE_ALTERNATIVES = 4096


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    kind: str
    section: int
    level: int


def trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


class BlockIndex:
    """Immutable positions from a pinned file, not a freshly rendered Markdown."""
    def __init__(self, documents: dict[str, str]):
        self.documents = dict(documents)
        self.hashes = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in documents.items()}
        self.blocks: dict[str, tuple[Block, ...]] = {}
        parser = MarkdownIt('commonmark').enable('table')
        for path, text in documents.items():
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            result: list[Block] = []
            section = -1
            for token in parser.parse(text):
                if token.map is None or token.type == 'inline' or token.nesting < 0:
                    continue
                root = token.level == 0
                # Only full root blocks and top-level list items. Never isolate
                # a paragraph inside a table, nested list or code fence.
                if not root and not (token.type == 'list_item_open' and token.level == 1):
                    continue
                if root and token.type == 'heading_open':
                    section = token.map[0]
                start, end = trim(text, offsets[token.map[0]], offsets[token.map[1]])
                if start == end:
                    continue
                kind = token.type.removesuffix('_open')
                if kind == 'fence':
                    # CommonMark accepts an unclosed fence; the experiment does
                    # not call that a complete code block.
                    closing = text[start:end].splitlines()[-1].strip()
                    if not re.fullmatch(re.escape(token.markup[0]) + '{' + str(len(token.markup)) + ',}', closing):
                        kind = 'unsupported'
                if kind == 'html_block':
                    kind = 'unsupported'
                result.append(Block(start, end, kind, section, token.level))
            if len(result) > MAX_DOCUMENT_BLOCKS:
                raise ValueError('Explicit document work limit exceeded')
            self.blocks[path] = tuple(result)

    def alternatives(self, source: dict[str, Any], raw: str) -> tuple[tuple[int, int], ...]:
        origin = source.get('_qualification_candidate', source)
        path = str(source.get('path_or_url') or origin.get('path') or '')
        start, end = origin.get('char_start'), origin.get('char_end')
        if (path not in self.documents or path != origin.get('path')
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(self.documents[path])
                or self.documents[path][start:end] != raw
                or origin.get('content') != raw):
            return ()
        blocks = self.blocks[path]
        contained = [b for b in blocks if start <= b.start < b.end <= end]
        spans: set[tuple[int, int]] = set()
        roots = [b for b in contained if b.level == 0]
        # Items are standalone options, but a complete list is always an option
        # as well. No number of characters determines which one is available.
        for b in contained:
            if b.kind not in {'heading', 'unsupported'}:
                spans.add((b.start, b.end))
        for i, left in enumerate(roots):
            if left.kind == 'unsupported':
                continue
            for right in roots[i:]:
                if right.section != left.section or right.kind == 'unsupported':
                    break
                if right.kind != 'heading':
                    spans.add((left.start, right.end))
                if len(spans) > MAX_CANDIDATE_ALTERNATIVES:
                    raise ValueError('Explicit candidate alternative work limit exceeded')
        # Do not offer a colon-ended lead-in without the list/code that follows.
        for i, b in enumerate(roots[:-1]):
            following = roots[i + 1]
            if (b.kind == 'paragraph' and self.documents[path][b.start:b.end].endswith(':')
                    and following.kind in {'bullet_list', 'ordered_list', 'fence', 'code_block', 'table'}
                    and following.section == b.section):
                spans = {(a, z) for a, z in spans if not (a <= b.start and z == b.end)}
        return tuple(sorted(((a - start, z - start) for a, z in spans), key=lambda v: (v[1] - v[0], v[0])))


def materialize(source, raw, start, end, source_line_start, query_text, assignments):
    candidate = dict(source)
    candidate['snippet'] = raw[start:end]
    candidate['line_start'], candidate['line_end'] = projection._focused_line_range(raw, start, end, source_line_start)
    candidate = projection._requalify_visible_source(candidate, query_text=query_text)
    return projection.bind_visible_assignments(source.get('_qualification_candidate', source), candidate, assignments)


@contextmanager
def installed(index: BlockIndex, diagnostics: dict[str, Any]):
    """No production mutation; restore both seams even when a test raises."""
    diagnostics.update(fragment_calls=[], expansions=[], oversize_expansions=0)

    def fragments(source, *, raw_snippet, query_ids, query_text, source_line_start,
                  obligations=(), assignments=()):
        options = index.alternatives(source, raw_snippet)
        variants = []
        for start, end in options:
            c = materialize(source, raw_snippet, start, end, source_line_start, query_text, assignments)
            if projection.qualified_query_ids((c,)) & query_ids or projection.component_witnesses(c, obligations):
                variants.append(c)
        variants.sort(key=lambda c: (
            len(projection.qualified_query_ids((c,)) & query_ids),
            len(projection.component_witnesses(c, obligations)),
            len(c.get('_visible_assignment_hashes') or ()),
            -len(c['snippet']),
        ), reverse=True)
        diagnostics['fragment_calls'].append({
            'path': source.get('path_or_url'),
            'candidate_start': source.get('_qualification_candidate', source).get('char_start'),
            'raw_chars': len(raw_snippet), 'available_ranges': options,
            'qualified': [{'start_line': c['line_start'], 'end_line': c['line_end'],
                           'chars': len(c['snippet']), 'snippet': c['snippet']} for c in variants],
        })
        return variants

    def expand(sources, *, projection_inputs, query_plan, public_query_ids, max_tokens,
               obligations=(), assignments=()):
        expanded = [dict(s) for s in sources]
        query_text = {str(q.get('query_id') or ''): str(q.get('text') or '')
                      for q in query_plan.get('queries', ()) if isinstance(q, dict)}
        for i in range(len(expanded)):
            source = expanded[i]
            values = projection_inputs.get(str(source.get('evidence_id') or ''))
            if values is None:
                continue
            raw, _, source_line_start = values
            old = raw.find(source['snippet'])
            if old < 0 or raw.find(source['snippet'], old + 1) >= 0:
                continue
            options = sorted(index.alternatives(source, raw), key=lambda v: (-(v[1] - v[0]), v[0]))
            for start, end in options:
                if (end - start <= len(source['snippet']) or not
                        (start <= old and old + len(source['snippet']) <= end)):
                    continue
                c = materialize(source, raw, start, end, source_line_start, query_text, assignments)
                ids = projection.qualified_query_ids((c,))
                if not ids and not projection.component_witnesses(c, obligations):
                    continue
                if not (projection.qualified_query_ids((source,)) & set(public_query_ids)) <= ids:
                    continue
                if not set(projection.component_witnesses(source, obligations)) <= set(projection.component_witnesses(c, obligations)):
                    continue
                origin = source.get('_qualification_candidate', source)
                retained = projection.visible_assignments(origin, c, assignments)
                if any(a not in retained for a in projection.visible_assignments(origin, source, assignments)):
                    continue
                candidate_sources = [*expanded[:i], c, *expanded[i + 1:]]
                decision = projection.context_selection_decision(candidate_sources, public_query_ids)
                tokens = projection.docs_context_budget_tokens(projection._payload(candidate_sources, decision=decision, query_plan=query_plan))
                if tokens > max_tokens:
                    diagnostics['oversize_expansions'] += 1
                    continue
                expanded = candidate_sources
                diagnostics['expansions'].append({'path': source['path_or_url'], 'before': source['snippet'],
                                                  'after': c['snippet'], 'full_dto_tokens': tokens})
                break
        return expanded

    with patch.object(projection, '_qualified_fragments', fragments), patch.object(projection, '_expand_selected_snippets', expand):
        yield
