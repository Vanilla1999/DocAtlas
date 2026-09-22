"""Private source coordinates and dependency proposals, never approval flags."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .query_reference_binding import ScopeKey


@dataclass(frozen=True, slots=True)
class SourceKey:
    scope: ScopeKey
    document_id: str
    canonical_path: str
    document_sha256: str


@dataclass(frozen=True, slots=True)
class SpanRef:
    source: SourceKey
    start: int
    end: int
    text_sha256: str


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    kind: Literal['heading', 'list', 'table', 'definition', 'anaphora', 'cause']
    parent: SpanRef
    child: SpanRef
    rule_id: str


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    set_id: str
    member_spans: tuple[SpanRef, ...]
    edges: tuple[DependencyEdge, ...]
    proposed_need_ids: tuple[str, ...]
