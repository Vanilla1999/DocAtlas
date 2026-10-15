"""Declared local source structures, not a general semantic ownership graph."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import re

from docmancer.core.structured_chunking import parse_markdown_parents, _atom_spans
from .evidence_set_types import SourceKey, SpanRef, DependencyEdge

_LIST = re.compile(r'^(?P<indent>[ \t]*)(?:[-*+]|\d+[.)])[ \t]+(?P<body>.+)', re.M)


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    nodes: tuple[tuple[str, SpanRef], ...]
    edges: tuple[DependencyEdge, ...]
    lists: tuple[tuple[SpanRef, tuple[SpanRef, ...]], ...]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def source_span(source: SourceKey, raw: str, start: int, end: int) -> SpanRef:
    # Strip only terminal line separators, never significant code spaces.
    while end > start and raw[end-1] in '\r\n':
        end -= 1
    return SpanRef(source, start, end, digest(raw[start:end]))


def _single_subject(text: str):
    """Compatibility adapter: prose ownership is unknown, not independent."""
    return None


def _list_parts(raw: str, source: SourceKey, start: int, end: int):
    text=raw[start:end]; matches=list(_LIST.finditer(text))
    if not matches:
        return None
    first=matches[0]; indent=len(first['indent'])
    intro=source_span(source,raw,start,start+first.start())
    if not raw[intro.start:intro.end].rstrip().endswith(':'):
        return None
    top=[m for m in matches if len(m['indent'])==indent]
    children=[]
    for index, item in enumerate(top):
        stop=top[index+1].start() if index+1<len(top) else len(text)
        children.append(source_span(source,raw,start+item.start(),start+stop))
    return (intro,tuple(children)) if children else None


def _table_parts(raw: str, source: SourceKey, start: int, end: int):
    text=raw[start:end]; lines=text.splitlines(keepends=True)
    if len(lines)<3 or '\\|' in text:
        return None
    cells=lambda line:[c.strip() for c in line.strip().strip('|').split('|')]
    header,sep=cells(lines[0]),cells(lines[1])
    if (len(header)<2 or not all(header) or len(header)!=len(sep)
            or not all(re.fullmatch(r':?-{3,}:?',c) for c in sep)):
        return None
    size=len(lines[0])+len(lines[1]); parent=source_span(source,raw,start,start+size)
    children=[];cursor=start+size
    for line in lines[2:]:
        row=cells(line)
        if len(row)==len(header) and all(row):
            children.append(source_span(source,raw,cursor,cursor+len(line)))
        cursor+=len(line)
    return (parent,tuple(children)) if children else None


@lru_cache(maxsize=16)
def source_graph(raw: str, source: SourceKey) -> DependencyGraph:
    """Cache only immutable parse inputs/edges; never query acceptance decisions."""
    if digest(raw)!=source.document_sha256:
        return DependencyGraph((),(),())
    nodes=[];edges=[];lists=[]
    for parent in parse_markdown_parents(raw, source.document_id):
        atoms=_atom_spans(raw,parent.char_start,parent.char_end)
        local=[];heading=None
        for atom in atoms:
            ref=source_span(source,raw,atom.start,atom.end)
            if ref.start>=ref.end or atom.atom_type=='whitespace':
                continue
            if atom.atom_type=='heading':
                first_line=raw.find('\n',atom.start,atom.end)
                heading=source_span(source,raw,atom.start,first_line if first_line>=0 else atom.end)
                local.append(('heading',heading))
                continue
            parts=(_list_parts(raw,source,atom.start,atom.end) if atom.atom_type=='list'
                   else _table_parts(raw,source,atom.start,atom.end) if atom.atom_type=='table' else None)
            if parts:
                intro,children=parts;kind=atom.atom_type
                local.append((kind+'_intro',intro));local.extend((kind+'_item',c) for c in children)
                rule='introduced-list-item-v1' if kind=='list' else 'markdown-table-row-v1'
                edges.extend(DependencyEdge(kind,intro,child,rule) for child in children)
                if kind=='list':lists.append((intro,children))
                continue
            local.append((atom.atom_type,ref))
        if heading:
            edges.extend(DependencyEdge('heading',heading,ref,'markdown-owning-heading-v1')
                         for kind,ref in local if kind!='heading')
        nodes.extend(local)
    return DependencyGraph(tuple(nodes),tuple(dict.fromkeys(edges)),tuple(lists))
