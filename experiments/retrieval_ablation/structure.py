"""Question-independent CommonMark canonicalization and source-local assembly.

Coordinates in derived Markdown refer to a separately hashed canonical extract,
never to unchanged bytes/lines of the raw input. This is an opt-in experiment;
the production parser, its token limits and contextual prefix are untouched.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
import re


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical_markdown(raw: str) -> dict:
    """Make source-declared top-level headings explicit for the real indexer.

    The CommonMark parser identifies structural boundaries; it does not execute
    HTML, includes, extensions, code or links. Unsupported ambiguous constructs
    fail closed instead of inventing an owner. No API names or question enter.
    """
    from markdown_it import MarkdownIt
    if not isinstance(raw, str) or '\x00' in raw:
        raise ValueError('expected UTF-8 Markdown without NUL')
    # The unchanged product index uses Python splitlines, while CommonMark
    # and the public audit use CR/LF and LF coordinates respectively. Refuse
    # incompatible controls instead of deleting a declaration at a shifted map.
    if re.search(r'[\v\f\x1c-\x1e\x85\u2028\u2029]|\r(?!\n)', raw):
        raise ValueError('BLOCKED_REPRESENTATION: incompatible line boundaries')
    lines = raw.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    replacements = []
    for token in MarkdownIt('commonmark').parse(raw):
        if token.type == 'html_block':
            raise ValueError('BLOCKED_REPRESENTATION: raw HTML needs a separate loader')
        if token.type == 'heading_open' and token.level == 0:
            begin, end = token.map
            first = lines[begin].rstrip('\r\n')
            newline = '\r\n' if lines[begin].endswith('\r\n') else '\n'
            if token.markup in ('-', '='):
                if end - begin != 2:
                    raise ValueError('BLOCKED_REPRESENTATION: multiline setext heading')
                text = '#' * int(token.tag[1:]) + ' ' + first.strip(' \t') + newline
                # Blank line replaces the underline. The original bytes are in
                # the frozen raw corpus and recorded edit; not silently lost.
                text += newline if lines[end-1].endswith(('\n', '\r')) else ''
            else:
                if end - begin != 1:
                    raise ValueError('BLOCKED_REPRESENTATION: ambiguous ATX heading')
                body = first.lstrip(' \t')[len(token.markup):].strip(' \t')
                body = re.sub(r'[ \t]+#+[ \t]*$', '', body)
                text = token.markup + ' ' + body + (newline if lines[begin].endswith('\n') else '')
            a, b = offsets[begin], offsets[end]
            if raw[a:b] != text:
                replacements.append((a, b, text, 'source_declared_heading'))
        if token.type == 'fence' and token.level == 0:
            begin, end = token.map
            # Only rewrite delimiters. A longer tilde marker cannot be closed by
            # an apparent fence inside the preserved source code body.
            close = lines[end-1].strip() if end > begin + 1 else ''
            closed = bool(re.fullmatch(re.escape(token.markup[0]) + '{' + str(len(token.markup)) + ',}', close))
            if not closed:
                raise ValueError('BLOCKED_REPRESENTATION: unterminated fence')
            middle = ''.join(lines[begin+1:end-1])
            max_tildes = max((len(m.group(1)) for m in re.finditer(r'^ {0,3}(~{3,})', middle, re.M)), default=2)
            marker = '~' * max(3, max_tildes + 1)
            newline = '\r\n' if lines[begin].endswith('\r\n') else '\n'
            opening = marker + token.info + newline
            closing = marker + (newline if lines[end-1].endswith('\n') else '')
            replacements.extend([(offsets[begin], offsets[begin+1], opening, 'fence_delimiter'),
                                 (offsets[end-1], offsets[end], closing, 'fence_delimiter')])
    replacements.sort()
    pieces, edits, copied, pos, canonical_pos = [], [], [], 0, 0
    for a, b, text, reason in replacements:
        if a < pos:
            raise ValueError('overlapping structural edits')
        prefix = raw[pos:a]
        if prefix:
            copied.append({'raw_span': [pos, a], 'canonical_span': [canonical_pos, canonical_pos+len(prefix)]})
        pieces.extend((prefix, text))
        canonical_pos += len(prefix)
        edits.append({'raw_span': [a, b], 'canonical_span': [canonical_pos, canonical_pos+len(text)],
                      'raw_text': raw[a:b], 'canonical_text': text, 'reason': reason})
        canonical_pos += len(text)
        pos = b
    pieces.append(raw[pos:])
    if pos < len(raw):
        copied.append({'raw_span': [pos, len(raw)], 'canonical_span': [canonical_pos, canonical_pos+len(raw)-pos]})
    canonical = ''.join(pieces)
    return {'text': canonical, 'raw_sha256': digest(raw), 'canonical_sha256': digest(canonical),
        'raw_bytes': len(raw.encode('utf-8')), 'canonical_bytes': len(canonical.encode('utf-8')),
        'converter': 'commonmark-source-structure-v1', 'parser': 'markdown-it-py',
        'parser_version': version('markdown-it-py'), 'parser_options': 'commonmark; no plugins',
        'citation_space': 'canonical_project_extract', 'edits': edits, 'copied_spans': copied}


def bounded_bundle(candidate: dict, original: dict) -> tuple[list, dict]:
    """Whole intersecting atoms plus at most one previous/next owner-local atom.

    No SQL, query terms, score, gold or full-parent expansion is used to choose
    the span. Disjoint required headings are separate cited entries, not a fake
    continuous quote. An oversized closure is omitted, not cut back to the seed.
    """
    from docmancer.core.structured_chunking import parse_markdown_parents
    from docmancer.docs.application.joint_context_candidates import _context_row, structural_spans
    from docmancer.docs.application.model_visible_projection import _docs_source
    from docmancer.docs.application.qualified_support_units import OriginKey, DeliveryUnit
    from docmancer.docs.domain.query_reference_binding import ScopeKey

    ref = original['_reference_evidence']
    raw, source = ref['raw_document'], ref['source']
    if digest(raw) != source['content_sha256']:
        raise ValueError('assembly snapshot mismatch')
    owner = ref.get('owner')
    trace = {'seed_id': candidate['stable_chunk_id'], 'neighbor_reads': 0,
             'neighbor_display_bytes': 0, 'extra_searches': 0, 'units': []}
    parents = parse_markdown_parents(raw, source['document_id'])
    parent = next((p for p in parents if owner and p.logical_id == owner['logical_id']), None)
    if parent is None or parent.level == 0:
        trace['status'] = 'NO_STRUCTURAL_OWNER_SEED_ONLY'
        return [(deepcopy(candidate), deepcopy(original))], trace
    a, b = ref['char_start'], ref['char_end']
    spans = [(x, y, kind) for x, y, kind in structural_spans(raw, parent.char_start, parent.char_end)
             if kind != 'whitespace']
    hit_indices = [i for i, (x, y, _) in enumerate(spans) if x < b and a < y]
    if not hit_indices:
        raise ValueError('seed has no structural atom')
    left, right = max(0, hit_indices[0]-1), min(len(spans)-1, hit_indices[-1]+1)
    neighbors = [spans[i] for i in range(left, right+1) if i not in hit_indices]
    trace['neighbor_reads'] = len(neighbors)
    trace['neighbor_display_bytes'] = sum(len(raw[x:y].encode('utf-8')) for x, y, _ in neighbors)
    start, end = spans[left][0], spans[right][1]
    header_start, header_end = owner['char_start'], owner['char_end']
    while header_end > header_start and raw[header_end-1].isspace():
        header_end -= 1
    trace['structural_document_bytes'] = len(raw.encode('utf-8'))
    trace['structural_owner_bytes'] = len(raw[parent.char_start:parent.char_end].encode('utf-8'))
    trace['owner_heading_reads'] = int(start > header_start)
    bounds = ([(header_start, header_end)] if start > header_start else []) + [(start, end)]
    public = _docs_source(original)
    if public is None:
        trace['status'] = 'UNRENDERABLE_SEED'
        return [], trace
    public.update(project_identity=original['project_identity'], scope=original.get('doc_scope', 'project'))
    origin = OriginKey(ScopeKey(**source['scope']), source['document_id'], source['content_sha256'],
                       0, len(raw), parent.logical_id,
                       digest(json.dumps(original['_reference_root_plan'], sort_keys=True)))
    bundle = []
    for x, y in bounds:
        proposal = _context_row(original, public, raw, parent, x, y, supplementary=False)
        if proposal is None:
            trace['status'] = 'OVERSIZED_OR_POLICY_REJECTED_ATOMIC_BUNDLE'
            return [], trace
        _, materialized = proposal
        new_ref = materialized['_reference_evidence']
        delivered_start, delivered_end = new_ref['char_start'], new_ref['char_end']
        unit = DeliveryUnit(origin, delivered_start, delivered_end,
                            digest(materialized['content']), frozenset(),
                            ((header_start, header_end),) if x > header_start else ())
        # These types are provenance, not a fabricated qualification certificate.
        trace['units'].append(asdict(unit))
        bundle.append(({**deepcopy(candidate), 'delivery_span': [delivered_start, delivered_end],
                        'delivery_role': 'owner_declaration' if (x, y) == (header_start, header_end) else 'evidence'}, materialized))
    trace['status'] = 'ASSEMBLED' if any(o['content'] != original['content'] for _, o in bundle) else 'UNCHANGED'
    return bundle, trace
