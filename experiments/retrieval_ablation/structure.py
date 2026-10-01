"""CommonMark heading maps over unchanged source bytes, for experimental B only."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

from docmancer.core import structured_chunking as core


def commonmark_parents(content, source_identity):
    from markdown_it import MarkdownIt

    if not content:
        return []
    _, offsets = core._line_offsets(content)
    tokens = MarkdownIt('commonmark').parse(content)
    headings = [(token.map[0], int(token.tag[1:]), tokens[i + 1].content)
                for i, token in enumerate(tokens)
                if token.type == 'heading_open' and token.level == 0]
    ranges = []
    stack, occurrences = [], {}
    if not headings:
        ranges.append((0, len(content), 'Document', 0, (), (), 1))
    elif offsets[headings[0][0]]:
        ranges.append((0, offsets[headings[0][0]], 'Introduction', 0, (), (), 1))
    for i, (line, level, title) in enumerate(headings):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        key = tuple(stack)
        occurrences[key] = occurrences.get(key, 0) + 1
        end = offsets[headings[i + 1][0]] if i + 1 < len(headings) else len(content)
        ranges.append((offsets[line], end, title, level,
                       tuple(x[1] for x in stack), tuple(x[0] for x in stack), occurrences[key]))
    parents = []
    source_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    for start, end, title, level, path, levels, occurrence in ranges:
        display = content[start:end]
        logical_id = 'parent-' + core._digest(core.SCHEMA_VERSION, source_identity,
            json.dumps(path, ensure_ascii=False), json.dumps(levels), str(occurrence))[:32]
        byte_start, byte_end, line_start, line_end = core._span_values(content, offsets, start, end)
        parents.append(core.ParentSection(
            logical_id=logical_id, revision_id='parent-rev-' + core._digest(logical_id,
                hashlib.sha256(display.encode('utf-8')).hexdigest())[:32],
            source_identity=source_identity, source_content_hash=source_hash,
            title=title, level=level, heading_path=path, heading_levels=levels,
            occurrence=occurrence, char_start=start, char_end=end,
            byte_start=byte_start, byte_end=byte_end, line_start=line_start,
            line_end=line_end, display_text=display))
    return parents


@contextmanager
def source_structure_parser():
    """Use one parser for indexing AND source-bound validation, then restore it.

    This is process-local test instrumentation, never a concurrent server hook.
    The production child atomizer, prefix, chunk limits, FTS and gates stay intact.
    """
    from docmancer.docs.domain.source_subject_binding import _document_structure
    original = core.parse_markdown_parents

    def aliases(function):
        for name, module in tuple(sys.modules.items()):
            if module is not None and name.startswith('docmancer.'):
                for key, value in tuple(vars(module).items()):
                    if value is function:
                        yield module, key

    identity = {'kind': 'commonmark_source_structure',
                'representation': 'source_bound_commonmark_v1',
                'parser': 'markdown-it-py', 'parser_version': version('markdown-it-py'),
                'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'contextual_prefix': 'production_unchanged', 'fts_weights': [6, 2, 0.5],
                'child_target_tokens': 160, 'child_hard_max_tokens': 512,
                'formats': ['native_markdown'], 'source_coordinates': 'original_utf8_markdown'}
    _document_structure.cache_clear()
    for module, key in aliases(original):
        setattr(module, key, commonmark_parents)
    try:
        yield identity
    finally:
        for module, key in aliases(commonmark_parents):
            setattr(module, key, original)
        _document_structure.cache_clear()
