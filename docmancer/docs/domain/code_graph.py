from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha1
from typing import Any

_FILE_NODE_KIND = "file"
_SYMBOL_NODE_KIND = "symbol"
_KNOWN_EDGE_KINDS = {
    "contains",
    "imports",
    "exports",
    "references",
    "unresolved_import",
    "unresolved_export",
    "unresolved_reference",
}
_CONFIDENCE_SCORES = {
    "exact": 1.0,
    "parser": 0.9,
    "regex": 0.7,
    "heuristic": 0.45,
    "unresolved": 0.1,
}


@dataclass
class CodeGraphNode:
    id: str
    kind: str
    name: str
    path: str
    language: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.path = _normalize_path(self.path)


@dataclass
class CodeGraphEdge:
    id: str
    kind: str
    from_node_id: str
    to_node_id: str | None = None
    from_path: str | None = None
    to_path: str | None = None
    symbol: str | None = None
    line_start: int | None = None
    confidence: str = "heuristic"
    confidence_score: float = 0.5
    evidence: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.from_path is not None:
            self.from_path = _normalize_path(self.from_path)
        if self.to_path is not None:
            self.to_path = _normalize_path(self.to_path)
        if self.confidence_score == 0.5:
            self.confidence_score = confidence_score_for(self.confidence)


@dataclass
class CodeGraph:
    nodes: list[CodeGraphNode]
    edges: list[CodeGraphEdge]
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def node_by_id(self) -> dict[str, CodeGraphNode]:
        return {node.id: node for node in self.nodes}

    def edges_by_from(self) -> dict[str, list[CodeGraphEdge]]:
        grouped: dict[str, list[CodeGraphEdge]] = {}
        for edge in self.edges:
            grouped.setdefault(edge.from_node_id, []).append(edge)
        return grouped

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "diagnostics": dict(self.diagnostics),
        }


def make_file_node_id(path: str) -> str:
    return f"file:{_normalize_path(path)}"


def make_symbol_node_id(path: str, symbol: str, line_start: int | None = None) -> str:
    return f"symbol:{_normalize_path(path)}:{line_start or 0}:{symbol}"


def make_edge_id(
    kind: str,
    from_node_id: str,
    to_node_id: str | None,
    symbol: str | None = None,
    line_start: int | None = None,
) -> str:
    identity = "\0".join([
        kind,
        from_node_id,
        to_node_id or "",
        symbol or "",
        str(line_start or 0),
    ])
    return f"edge:{sha1(identity.encode('utf-8')).hexdigest()[:16]}"


def confidence_score_for(confidence: str) -> float:
    return _CONFIDENCE_SCORES.get(confidence, _CONFIDENCE_SCORES["heuristic"])


def _normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").strip("/")
