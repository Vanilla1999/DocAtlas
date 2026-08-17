"""Implementation shard 2 for code_graph."""
from __future__ import annotations

from ._code_graph_shared import *  # noqa: F401,F403

from ._code_graph_part01 import CodeGraph, CodeGraphEdge, CodeGraphNode, CodeGraphPath, _code_graph_path_from_ids, _connected_target_ids, _contains_term, _context_query_terms, _file_strings, _normalize_match_text, _path_adjacency, _path_node_matches, _path_sort_text, _sort_edges, _sort_nodes, _symbols_for_file

def build_code_graph_context_items(
    graph: CodeGraph,
    *,
    question: str = "",
    token_budget: int = 1200,
    max_items: int = 8,
) -> list[dict[str, Any]]:
    if token_budget <= 0 or max_items <= 0:
        return []
    file_nodes = [node for node in graph.nodes if node.kind == "file"]
    if not file_nodes:
        return []
    scored = [(node, *_score_code_graph_file_detail(graph, node, question=question)) for node in file_nodes]
    scored.sort(key=lambda item: (-item[1], item[0].path))
    selected = [item for item in scored if item[1] > 0]
    if not selected:
        selected = scored[:2]

    items: list[dict[str, Any]] = []
    used_tokens = 0
    for file_node, score, reasons, breakdown in selected:
        if len(items) >= max_items:
            break
        item = _code_graph_context_item(graph, file_node, question=question, score=score, score_reasons=reasons, score_breakdown=breakdown, token_budget=token_budget)
        estimate = int(item["token_estimate"])
        if items and used_tokens + estimate > token_budget:
            continue
        items.append(item)
        used_tokens += estimate
    return items


def score_code_graph_file(
    graph: CodeGraph,
    file_node: CodeGraphNode,
    *,
    question: str,
) -> tuple[float, list[str]]:
    score, reasons, _breakdown = _score_code_graph_file_detail(graph, file_node, question=question)
    return score, reasons


def _score_code_graph_file_detail(
    graph: CodeGraph,
    file_node: CodeGraphNode,
    *,
    question: str,
) -> tuple[float, list[str], list[dict[str, Any]]]:
    terms = _context_query_terms(question)
    use_intent = _has_reference_intent(question)
    breakdown: list[dict[str, Any]] = []
    seen_breakdown: set[tuple[str, str]] = set()
    edges = _edges_for_file(graph, file_node.id)
    symbols = _symbols_for_file(graph, file_node.path)
    strings = _file_strings(file_node)

    def add(reason: str, points: float, evidence: str, confidence: str) -> None:
        if points <= 0:
            return
        key = (reason, str(evidence))
        if key in seen_breakdown:
            return
        seen_breakdown.add(key)
        breakdown.append({
            "reason": reason,
            "points": round(points, 3),
            "evidence": str(evidence)[:80],
            "confidence": confidence,
        })

    for term in terms:
        for symbol in symbols:
            if not _contains_term(symbol.name, term):
                continue
            confidence = str(symbol.metadata.get("extraction_confidence") or ("parser" if file_node.language == "python" else "regex"))
            points = 0.5 if _is_low_signal_symbol(symbol.name) else 5.0
            add("symbol_match", points, symbol.name, confidence)
        for value in strings:
            if _contains_term(value, term):
                add("string_or_status_match", 8.0, value, "exact")
        if _contains_term(file_node.path, term):
            add("path_match", 5.0, file_node.path, "exact")
        for matched in file_node.metadata.get("matched_terms") or []:
            if _contains_term(str(matched), term):
                add("source_evidence_term", 4.0, str(matched), "heuristic")
        for edge in edges:
            if edge.kind == "references" and edge.symbol and _contains_term(edge.symbol, term):
                points = _edge_relevance_weight(edge)
                if _is_low_signal_symbol(edge.symbol):
                    points = min(points, 0.5)
                add("reference_match", points, edge.symbol, edge.confidence)
                if use_intent and points > 0.5:
                    add("reference_intent_match", 7.0, edge.symbol, edge.confidence)
            elif edge.kind == "unresolved_reference" and edge.symbol and _contains_term(edge.symbol, term):
                add("unresolved_reference_search_hint", _edge_relevance_weight(edge), edge.symbol, "unresolved")
            elif edge.kind in {"imports", "exports"} and (_contains_term(edge.to_path or "", term) or _contains_term(edge.symbol or "", term)):
                add("import_or_export_match", _edge_relevance_weight(edge), edge.to_path or edge.symbol or edge.kind, edge.confidence)
            elif edge.kind in {"unresolved_import", "unresolved_export"} and _contains_term(edge.symbol or edge.evidence or "", term):
                add("unresolved_import_search_hint", _edge_relevance_weight(edge), edge.symbol or edge.evidence or edge.kind, "unresolved")

    local_edges = [edge for edge in edges if edge.kind in {"imports", "exports", "references"} and edge.to_path]
    has_direct_evidence = any(item["reason"] in {"symbol_match", "string_or_status_match", "path_match", "source_evidence_term", "reference_match", "unresolved_reference_search_hint"} for item in breakdown)
    if local_edges and _is_connected_to_matched_file(graph, file_node, terms):
        boost = 1.0 if has_direct_evidence else 0.6
        add("connected_to_matched_file", boost, file_node.path, "heuristic")

    score = round(sum(float(item["points"]) for item in breakdown), 3)
    reasons = [f"{item['reason']}:{item['evidence']}:+{item['points']}[{item['confidence']}]" for item in breakdown]
    return score, reasons, breakdown


def code_graph_diagnostics(graph: CodeGraph) -> dict[str, Any]:
    edge_kinds = Counter(edge.kind for edge in graph.edges)
    confidence_summary = Counter(edge.confidence for edge in graph.edges)
    file_nodes = [node for node in graph.nodes if node.kind == "file"]
    symbol_nodes = [node for node in graph.nodes if node.kind == "symbol"]
    selected_paths = [str(path) for path in graph.diagnostics.get("selected_paths") or [node.path for node in _sort_nodes(file_nodes)] if path]
    languages = sorted({str(node.language) for node in graph.nodes if node.language})
    return {
        "status": graph.diagnostics.get("status", "ok" if graph.nodes or graph.edges else "empty"),
        "graph_scope": graph.diagnostics.get("graph_scope", "selected_files"),
        "selected_files": int(graph.diagnostics.get("selected_files") or len(file_nodes)),
        "selected_paths": selected_paths[:20],
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "file_node_count": len(file_nodes),
        "symbol_node_count": len(symbol_nodes),
        "edge_kinds": dict(sorted(edge_kinds.items())),
        "confidence_summary": dict(sorted(confidence_summary.items())),
        "unresolved_import_count": edge_kinds.get("unresolved_import", 0) + edge_kinds.get("unresolved_export", 0),
        "unresolved_reference_count": edge_kinds.get("unresolved_reference", 0),
        "languages": languages[:20],
        "limitations": list(graph.diagnostics.get("limitations") or [
            "not_call_graph",
            "name_based_reference_resolution",
            "regex_symbols_for_non_python",
        ])[:20],
    }


def code_graph_context_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    edge_kinds: Counter[str] = Counter()
    confidence_summary: Counter[str] = Counter()
    score_reasons_by_path: dict[str, list[str]] = {}
    for item in items:
        metadata = item.get("metadata") or {}
        edge_kinds.update(metadata.get("edge_kinds") or [])
        confidence_summary.update(metadata.get("confidence_summary") or {})
        path = str(item.get("path") or "")
        if path:
            score_reasons_by_path[path] = [str(reason) for reason in metadata.get("score_reasons") or []][:8]
    return {
        "selected_items": len(items),
        "token_estimate": sum(int(item.get("token_estimate") or 0) for item in items),
        "paths": [item.get("path") for item in items][:20],
        "edge_kinds": dict(sorted(edge_kinds.items())),
        "confidence_summary": dict(sorted(confidence_summary.items())),
        "score_reasons_by_path": dict(sorted(score_reasons_by_path.items())),
    }


def find_code_graph_paths(
    graph: CodeGraph,
    *,
    start_terms: Sequence[str],
    target_terms: Sequence[str] | None = None,
    max_depth: int = 2,
    max_paths: int = 5,
) -> list[CodeGraphPath]:
    if max_depth <= 0 or max_paths <= 0:
        return []
    nodes_by_id = graph.node_by_id()
    start_keys = _path_query_terms(start_terms)
    target_keys = _path_query_terms(target_terms or [])
    if not start_keys:
        return []
    start_ids = [node.id for node in _sort_nodes(graph.nodes) if _path_node_matches(graph, node, start_keys)]
    if not start_ids:
        return []
    target_ids: set[str]
    if target_keys:
        target_ids = {node.id for node in graph.nodes if _path_node_matches(graph, node, target_keys)}
    else:
        target_ids = _connected_target_ids(graph, start_ids)
    if not target_ids:
        return []

    adjacency = _path_adjacency(graph)
    found: list[CodeGraphPath] = []
    for start_id in start_ids[:20]:
        frontier: list[tuple[str, list[str], list[CodeGraphEdge]]] = [(start_id, [start_id], [])]
        for _depth in range(max_depth):
            next_frontier: list[tuple[str, list[str], list[CodeGraphEdge]]] = []
            for current_id, node_path, edge_path in frontier[:50]:
                for next_id, edge in adjacency.get(current_id, [])[:50]:
                    if next_id in node_path or next_id not in nodes_by_id:
                        continue
                    new_nodes = [*node_path, next_id]
                    new_edges = [*edge_path, edge]
                    if next_id in target_ids:
                        found.append(_code_graph_path_from_ids(nodes_by_id, new_nodes, new_edges))
                        if len(found) >= max_paths * 3:
                            break
                    next_frontier.append((next_id, new_nodes, new_edges))
                if len(found) >= max_paths * 3:
                    break
            frontier = next_frontier[:50]
            if len(found) >= max_paths * 3:
                break
    deduped: dict[str, CodeGraphPath] = {}
    for path in found:
        key = "|".join([*(node.id for node in path.nodes), *(edge.id for edge in path.edges)])
        deduped.setdefault(key, path)
    paths = list(deduped.values())
    paths.sort(key=lambda path: (-path.confidence_score, len(path.edges), _path_sort_text(path)))
    return paths[:max_paths]


def render_code_graph_path(path: CodeGraphPath) -> str:
    if not path.nodes:
        return ""
    lines = [path.nodes[0].path]
    for edge, node in zip(path.edges, path.nodes[1:], strict=False):
        lines.append(f"  --{edge.kind}[{edge.confidence}]-->")
        lines.append(node.path)
    return "\n".join(lines)


def _path_query_terms(values: Sequence[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        text = str(value)
        if "/" in text or "\\" in text:
            normalized = _normalize_match_text(text)
            if normalized:
                terms.add(normalized)
            continue
        terms.update(_context_query_terms(text))
    return terms


def _is_low_signal_symbol(name: str) -> bool:
    normalized = re.sub(r"[^A-Za-z0-9]+", "", str(name or "")).casefold()
    return normalized in {
        "state",
        "widget",
        "buildcontext",
        "string",
        "future",
        "list",
        "map",
        "error",
        "result",
        "service",
        "repository",
        "cubit",
    }


def _edge_relevance_weight(edge: CodeGraphEdge) -> float:
    if edge.kind in {"unresolved_import", "unresolved_export"}:
        return 0.0 if edge.metadata.get("external") is True else 0.2
    if edge.kind == "unresolved_reference":
        return 0.3
    if edge.kind in {"imports", "exports"}:
        if not edge.to_path or edge.metadata.get("external") is True:
            return 0.0
        return 2.0 if edge.confidence == "exact" else 1.3
    if edge.kind == "references":
        return 2.5 if edge.confidence in {"heuristic", "regex", "parser", "exact"} else 1.0
    if edge.kind == "contains":
        return 5.0 if edge.confidence in {"parser", "regex", "exact"} else 0.5
    return 0.0


def _code_graph_context_item(
    graph: CodeGraph,
    file_node: CodeGraphNode,
    *,
    question: str,
    score: float,
    score_reasons: list[str],
    score_breakdown: list[dict[str, Any]],
    token_budget: int,
) -> dict[str, Any]:
    symbols = _symbols_for_file(graph, file_node.path)[:6]
    edges = _display_edges_for_file(graph, file_node.id)[:6]
    strings = _file_strings(file_node)[:4]
    linked_paths = [path for path, _reason in _linked_paths(edges)[:4]]
    title = f"Code graph: {file_node.path}"
    paths = find_code_graph_paths(
        graph,
        start_terms=[file_node.path, *strings],
        target_terms=linked_paths or [symbol.name for symbol in symbols],
        max_depth=2,
        max_paths=2,
    )
    paths = [path for path in paths if path.nodes and path.nodes[0].path == file_node.path][:2]
    content = _render_code_graph_content(file_node, symbols, edges, strings, paths)
    content = _fit_content_to_budget(content, token_budget)
    token_estimate = _estimate_tokens(content)
    edge_kinds = [edge.kind for edge in edges]
    confidence_summary = dict(sorted(Counter(edge.confidence for edge in edges).items()))
    return {
        "source_class": "code_graph",
        "path": file_node.path,
        "title": title,
        "language": file_node.language,
        "freshness": "current",
        "line_start": file_node.line_start,
        "line_end": file_node.line_end,
        "content": content,
        "token_estimate": token_estimate,
        "why_selected": "; ".join(score_reasons) if score_reasons else "structural code graph context",
        "source": {
            "source_class": "code_graph",
            "path": file_node.path,
            "title": title,
        },
        "section": {
            "title": title,
            "heading_path": "code_graph",
            "freshness": "current",
        },
        "metadata": {
            "node_ids": [file_node.id, *[symbol.id for symbol in symbols]],
            "edge_ids": [edge.id for edge in edges],
            "edge_kinds": edge_kinds,
            "linked_paths": linked_paths,
            "symbols": [symbol.name for symbol in symbols],
            "confidence_summary": confidence_summary,
            "score": score,
            "score_reasons": score_reasons,
            "score_breakdown": score_breakdown[:20],
        },
    }


def _render_code_graph_content(
    file_node: CodeGraphNode,
    symbols: list[CodeGraphNode],
    edges: list[CodeGraphEdge],
    strings: list[str],
    paths: list[CodeGraphPath] | None = None,
) -> str:
    lines = [f"Code graph slice: {file_node.path}"]
    if symbols:
        lines.append("Defines:")
        for symbol in symbols:
            symbol_kind = symbol.metadata.get("symbol_kind") or "symbol"
            lines.append(f"- {symbol_kind} {symbol.name}:{symbol.line_start or 0}")
    imports = [edge for edge in edges if edge.kind in {"imports", "exports", "unresolved_import", "unresolved_export"}]
    references = [edge for edge in edges if edge.kind in {"references", "unresolved_reference"}]
    if imports:
        lines.append("Imports:")
        for edge in imports:
            target = edge.to_path or "unresolved"
            lines.append(f"- {target} [{edge.kind}, {edge.confidence}]")
    if references:
        lines.append("References:")
        for edge in references:
            target = edge.to_path or "unresolved"
            symbol = edge.symbol or "reference"
            lines.append(f"- {symbol} -> {target} [{edge.kind}, {edge.confidence}]")
    if strings:
        lines.append("Strings:")
        for value in strings:
            lines.append(f"- {value!r}")
    linked = _linked_paths(edges)[:4]
    if linked:
        lines.append("Likely linked files:")
        for path, reason in linked:
            lines.append(f"- {path} via {reason}")
    if paths:
        lines.append("Likely paths:")
        for path in paths[:2]:
            compact = " -> ".join(node.path for node in path.nodes if node.kind == "file")
            if compact:
                lines.append(f"- {compact} ({path.explanation})")
    return "\n".join(lines)


def _fit_content_to_budget(content: str, token_budget: int) -> str:
    if _estimate_tokens(content) <= token_budget:
        return content
    kept: list[str] = []
    for line in content.splitlines():
        candidate = "\n".join([*kept, line])
        if kept and _estimate_tokens(candidate) > token_budget:
            break
        kept.append(line)
    return "\n".join(kept) if kept else content[: max(4, token_budget * 4)]


def _estimate_tokens(content: str) -> int:
    return max(1, len(content) // 4)


def _display_edges_for_file(graph: CodeGraph, file_node_id: str) -> list[CodeGraphEdge]:
    edges = [edge for edge in graph.edges if edge.from_node_id == file_node_id and edge.kind != "contains"]
    return _sort_edges(edges)


def _edges_for_file(graph: CodeGraph, file_node_id: str) -> list[CodeGraphEdge]:
    return [edge for edge in graph.edges if edge.from_node_id == file_node_id]


def _linked_paths(edges: list[CodeGraphEdge]) -> list[tuple[str, str]]:
    linked: list[tuple[str, str]] = []
    seen: set[str] = set()
    for edge in edges:
        if edge.to_path and edge.to_path not in seen:
            linked.append((edge.to_path, edge.kind))
            seen.add(edge.to_path)
    return linked


def _is_connected_to_matched_file(graph: CodeGraph, file_node: CodeGraphNode, terms: set[str]) -> bool:
    if not terms:
        return False
    node_by_path = {node.path: node for node in graph.nodes if node.kind == "file"}
    for edge in graph.edges:
        if edge.from_path == file_node.path and edge.to_path:
            target = node_by_path.get(edge.to_path)
            if target and _file_matches_terms(graph, target, terms):
                return True
        if edge.to_path == file_node.path and edge.from_path:
            source = node_by_path.get(edge.from_path)
            if source and _file_matches_terms(graph, source, terms):
                return True
    return False


def _file_matches_terms(graph: CodeGraph, file_node: CodeGraphNode, terms: set[str]) -> bool:
    symbols = _symbols_for_file(graph, file_node.path)
    strings = _file_strings(file_node)
    return any(
        _contains_term(file_node.path, term)
        or any(_contains_term(symbol.name, term) for symbol in symbols)
        or any(_contains_term(value, term) for value in strings)
        for term in terms
    )


def _has_reference_intent(question: str) -> bool:
    normalized = _normalize_match_text(question)
    return any(marker in normalized for marker in ("использ", "usage", "used", "uses", "use", "reference", "references"))

__all__=['build_code_graph_context_items', 'score_code_graph_file', '_score_code_graph_file_detail', 'code_graph_diagnostics', 'code_graph_context_diagnostics', 'find_code_graph_paths', 'render_code_graph_path', '_path_query_terms', '_is_low_signal_symbol', '_edge_relevance_weight', '_code_graph_context_item', '_render_code_graph_content', '_fit_content_to_budget', '_estimate_tokens', '_display_edges_for_file', '_edges_for_file', '_linked_paths', '_is_connected_to_matched_file', '_file_matches_terms', '_has_reference_intent']
