"""Implementation shard 1 for code_graph."""
from __future__ import annotations

from ._code_graph_shared import *  # noqa: F401,F403

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


@dataclass
class CodeGraphPath:
    nodes: list[CodeGraphNode]
    edges: list[CodeGraphEdge]
    confidence_score: float
    explanation: str


def build_project_code_graph(
    project_root: str | Path,
    *,
    question: str = "",
    requirements: Sequence[str] | None = None,
    max_files: int = 24,
    token_budget: int = 4000,
    include_unmatched: bool = False,
) -> CodeGraph:
    root = Path(project_root).expanduser().resolve()
    if max_files <= 0 or token_budget <= 0 or not root.exists() or not root.is_dir():
        return CodeGraph(nodes=[], edges=[], diagnostics={"status": "invalid_root"})

    facts = collect_project_source_facts(
        root,
        question=_merge_question_requirements(question, requirements),
        max_files=max_files,
        token_budget=token_budget,
        include_unmatched=include_unmatched,
    )
    all_paths = {str(item.get("path") or "") for item in facts if item.get("path")}
    nodes: list[CodeGraphNode] = []
    edges: list[CodeGraphEdge] = []

    for item in facts:
        path = _normalize_path(str(item.get("path") or ""))
        if not path:
            continue
        language = str(item.get("language") or "") or None
        file_node_id = make_file_node_id(path)
        nodes.append(CodeGraphNode(
            id=file_node_id,
            kind="file",
            name=Path(path).name,
            path=path,
            language=language,
            line_start=_optional_int(item.get("line_start")),
            line_end=_optional_int(item.get("line_end")),
            metadata={
                "line_count": item.get("line_count"),
                "char_count": item.get("char_count"),
                "selection_score": item.get("selection_score"),
                "matched_terms": list(item.get("matched_terms") or []),
                "string_literals": list(item.get("string_literals") or [])[:8],
                "status_like_tokens": list(item.get("status_like_tokens") or [])[:8],
            },
        ))
        extraction_confidence = "parser" if language == "python" else "regex"
        for symbol in item.get("symbols") or []:
            symbol_name = str(symbol.get("name") or "")
            if not symbol_name:
                continue
            line_start = _optional_int(symbol.get("line_start"))
            line_end = _optional_int(symbol.get("line_end"))
            symbol_node_id = make_symbol_node_id(path, symbol_name, line_start)
            symbol_kind = str(symbol.get("kind") or "symbol")
            nodes.append(CodeGraphNode(
                id=symbol_node_id,
                kind="symbol",
                name=symbol_name,
                path=path,
                language=language,
                line_start=line_start,
                line_end=line_end,
                metadata={
                    "symbol_kind": symbol_kind,
                    "extraction_confidence": extraction_confidence,
                    **({"parent": symbol["parent"]} if symbol.get("parent") else {}),
                },
            ))
            edges.append(CodeGraphEdge(
                id=make_edge_id("contains", file_node_id, symbol_node_id, symbol=symbol_name, line_start=line_start),
                kind="contains",
                from_node_id=file_node_id,
                to_node_id=symbol_node_id,
                from_path=path,
                to_path=path,
                symbol=symbol_name,
                line_start=line_start,
                confidence=extraction_confidence,
                evidence=f"{symbol_kind} {symbol_name}:{line_start or 0}",
            ))

    nodes = _dedupe_nodes(nodes)
    known_node_ids = {node.id for node in nodes}
    symbol_index = _build_symbol_index(nodes)
    for item in facts:
        path = _normalize_path(str(item.get("path") or ""))
        if not path:
            continue
        file_node_id = make_file_node_id(path)
        language = str(item.get("language") or "")
        imports = list(item.get("imports") or [])
        for import_value in _extra_import_values(str(item.get("content") or ""), language):
            if import_value not in imports:
                imports.append(import_value)
        for import_value in imports:
            resolved_path, confidence, metadata = _resolve_import_to_path(
                str(import_value),
                from_path=path,
                language=language,
                all_paths=all_paths,
                root=root,
            )
            if resolved_path:
                target_node_id = make_file_node_id(resolved_path)
                if target_node_id not in known_node_ids:
                    nodes.append(CodeGraphNode(
                        id=target_node_id,
                        kind="file",
                        name=Path(resolved_path).name,
                        path=resolved_path,
                        metadata={"not_selected_in_context": True},
                    ))
                    known_node_ids.add(target_node_id)
                edges.append(CodeGraphEdge(
                    id=make_edge_id("imports", file_node_id, target_node_id, symbol=str(import_value)),
                    kind="imports",
                    from_node_id=file_node_id,
                    to_node_id=target_node_id,
                    from_path=path,
                    to_path=resolved_path,
                    symbol=str(import_value),
                    confidence=confidence,
                    evidence=str(import_value),
                    metadata=metadata,
                ))
            else:
                edges.append(CodeGraphEdge(
                    id=make_edge_id("unresolved_import", file_node_id, None, symbol=str(import_value)),
                    kind="unresolved_import",
                    from_node_id=file_node_id,
                    from_path=path,
                    symbol=str(import_value),
                    confidence="unresolved",
                    confidence_score=confidence_score_for("unresolved"),
                    evidence=str(import_value),
                    metadata={"import_value": str(import_value), **metadata},
                ))
        for reference in item.get("references") or []:
            edges.extend(_reference_edges_for(str(reference), file_node_id=file_node_id, from_path=path, symbol_index=symbol_index))

    nodes = _sort_nodes(_dedupe_nodes(nodes))
    edges = _sort_edges(_dedupe_edges(edges))
    return CodeGraph(
        nodes=nodes,
        edges=edges,
        diagnostics=_graph_diagnostics(facts, nodes, edges, max_files=max_files, token_budget=token_budget),
    )


def _path_node_matches(graph: CodeGraph, node: CodeGraphNode, terms: set[str]) -> bool:
    if not terms:
        return False
    if any(_contains_term(node.path, term) or _contains_term(node.name, term) for term in terms):
        return True
    if node.kind == "file":
        if any(any(_contains_term(value, term) for term in terms) for value in _file_strings(node)):
            return True
        return any(any(_contains_term(symbol.name, term) for term in terms) for symbol in _symbols_for_file(graph, node.path))
    return False


def _connected_target_ids(graph: CodeGraph, start_ids: list[str]) -> set[str]:
    allowed = _path_adjacency(graph)
    targets: set[str] = set()
    for start_id in start_ids:
        for node_id, _edge in allowed.get(start_id, []):
            targets.add(node_id)
    return targets


def _path_adjacency(graph: CodeGraph) -> dict[str, list[tuple[str, CodeGraphEdge]]]:
    allowed = {"imports", "exports", "references", "contains"}
    adjacency: dict[str, list[tuple[str, CodeGraphEdge]]] = {}
    for edge in _sort_edges(graph.edges):
        if edge.kind not in allowed or not edge.to_node_id:
            continue
        adjacency.setdefault(edge.from_node_id, []).append((edge.to_node_id, edge))
        adjacency.setdefault(edge.to_node_id, []).append((edge.from_node_id, edge))
    return adjacency


def _code_graph_path_from_ids(nodes_by_id: dict[str, CodeGraphNode], node_ids: list[str], edges: list[CodeGraphEdge]) -> CodeGraphPath:
    confidence = _path_confidence(edges)
    return CodeGraphPath(
        nodes=[nodes_by_id[node_id] for node_id in node_ids],
        edges=edges,
        confidence_score=confidence,
        explanation=_path_explanation(edges),
    )


def _path_confidence(edges: list[CodeGraphEdge]) -> float:
    if not edges:
        return 0.0
    avg = sum(edge.confidence_score for edge in edges) / len(edges)
    return round(avg * (0.9 ** max(0, len(edges) - 1)), 4)


def _path_explanation(edges: list[CodeGraphEdge]) -> str:
    kinds = {edge.kind for edge in edges}
    if "references" in kinds and not (kinds & {"imports", "exports"}):
        return "Likely linked through name-based reference; inspect both files."
    if kinds <= {"imports", "exports"}:
        return "Linked through local import edge."
    return "Likely implementation path based on local imports/references."


def _path_sort_text(path: CodeGraphPath) -> str:
    return "|".join([*(node.path for node in path.nodes), *(edge.kind for edge in path.edges)])


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


def _symbols_for_file(graph: CodeGraph, path: str) -> list[CodeGraphNode]:
    return [node for node in _sort_nodes(graph.nodes) if node.kind == "symbol" and node.path == path]


def _file_strings(file_node: CodeGraphNode) -> list[str]:
    values: list[str] = []
    for key in ("string_literals", "status_like_tokens"):
        for value in file_node.metadata.get(key) or []:
            text = str(value)
            if text not in values:
                values.append(text)
    return values


def _context_query_terms(question: str) -> set[str]:
    terms: set[str] = set()
    for quoted in re.findall(r'"([^"]+)"|\'([^\']+)\'', question):
        value = quoted[0] or quoted[1]
        normalized = _normalize_match_text(value)
        if normalized:
            terms.add(normalized)
    for word in re.findall(r"[\w\-]+", question, flags=re.UNICODE):
        normalized_word = _normalize_match_text(word)
        if len(normalized_word) >= 3:
            terms.add(normalized_word)
        for key in _symbol_keys(word):
            if len(key) >= 3:
                terms.add(key)
    return terms


def _contains_term(value: str, term: str) -> bool:
    normalized = _normalize_match_text(value)
    compact = re.sub(r"\s+", "", normalized)
    return term in normalized or term in compact


def _normalize_match_text(value: str) -> str:
    split = _CAMEL_SPLIT_RE.sub(" ", str(value).replace("_", " ").replace("-", " ").replace("/", " "))
    return re.sub(r"\s+", " ", split).strip().casefold()


def _resolve_import_to_path(
    import_value: str,
    *,
    from_path: str,
    language: str,
    all_paths: set[str],
    root: Path,
) -> tuple[str | None, str, dict[str, Any]]:
    value = import_value.strip()
    metadata: dict[str, Any] = {"import_value": value}
    if not value:
        return None, "unresolved", {**metadata, "external": False, "reason": "empty_import"}
    if language == "dart":
        return _resolve_dart_import(value, from_path=from_path, all_paths=all_paths, root=root, metadata=metadata)
    if language == "python":
        return _resolve_python_import(value, from_path=from_path, all_paths=all_paths, metadata=metadata)
    if language in {"javascript", "typescript"}:
        return _resolve_js_ts_import(value, from_path=from_path, all_paths=all_paths, metadata=metadata)
    return _resolve_common_import(value, from_path=from_path, all_paths=all_paths, extensions=(), metadata=metadata)


def _resolve_dart_import(value: str, *, from_path: str, all_paths: set[str], root: Path, metadata: dict[str, Any]) -> tuple[str | None, str, dict[str, Any]]:
    if value.startswith("dart:"):
        return _resolution_result(None, metadata, resolver="dart_sdk", reason="dart_sdk_import", external=True, attempted_paths=[], confidence="unresolved")
    if value.startswith("package:"):
        package, _, package_path = value.removeprefix("package:").partition("/")
        project_name = _pubspec_name(root)
        if project_name and package == project_name and package_path:
            bases = [f"lib/{package_path}"]
            resolved, attempted, matches = _resolve_candidates(bases, all_paths, _DART_EXTENSIONS)
            if resolved:
                return _resolution_result(resolved, metadata, resolver="dart_package_self", reason="pubspec_package_self", external=False, attempted_paths=attempted, confidence="exact")
            if len(matches) > 1:
                return _ambiguous_resolution(metadata, resolver="dart_package_self", attempted_paths=attempted, matches=matches)
            return _resolution_result(None, metadata, resolver="dart_package_self", reason="package_self_path_not_found", external=False, attempted_paths=attempted, confidence="unresolved")
        return _resolution_result(None, metadata, resolver="dart_external_package", reason="external_dart_package", external=True, attempted_paths=[], confidence="unresolved")
    return _resolve_common_import(
        value,
        from_path=from_path,
        all_paths=all_paths,
        extensions=_DART_EXTENSIONS,
        metadata=metadata,
        resolver="dart_relative",
        bare_relative=True,
    )


def _resolve_python_import(value: str, *, from_path: str, all_paths: set[str], metadata: dict[str, Any]) -> tuple[str | None, str, dict[str, Any]]:
    parts = [part for part in value.split(".") if part]
    attempted_all: list[str] = []
    for end in range(len(parts), 0, -1):
        base = "/".join(parts[:end])
        resolved, attempted, matches = _resolve_candidates([base], all_paths, _PY_EXTENSIONS)
        attempted_all.extend(attempted)
        if resolved:
            return _resolution_result(resolved, metadata, resolver="python_dotted", reason="python_module_path_guess", external=False, attempted_paths=attempted_all, confidence="heuristic")
        if len(matches) > 1:
            return _ambiguous_resolution(metadata, resolver="python_dotted", attempted_paths=attempted_all, matches=matches)
    from_dir = posixpath.dirname(from_path)
    for end in range(len(parts), 0, -1):
        base = posixpath.normpath(posixpath.join(from_dir, "/".join(parts[:end])))
        resolved, attempted, matches = _resolve_candidates([base], all_paths, _PY_EXTENSIONS)
        attempted_all.extend(attempted)
        if resolved:
            return _resolution_result(resolved, metadata, resolver="python_relative_guess", reason="python_relative_module_path_guess", external=False, attempted_paths=attempted_all, confidence="heuristic")
        if len(matches) > 1:
            return _ambiguous_resolution(metadata, resolver="python_relative_guess", attempted_paths=attempted_all, matches=matches)
    return _resolution_result(None, metadata, resolver="python_dotted", reason="python_module_not_found", external=bool(parts and parts[0] not in {"app", "lib", "src"}), attempted_paths=attempted_all, confidence="unresolved")


def _resolve_js_ts_import(value: str, *, from_path: str, all_paths: set[str], metadata: dict[str, Any]) -> tuple[str | None, str, dict[str, Any]]:
    return _resolve_common_import(
        value,
        from_path=from_path,
        all_paths=all_paths,
        extensions=_JS_TS_EXTENSIONS,
        metadata=metadata,
        resolver="ts_relative" if value.startswith(('.', '/', '..')) else "ts_project_path",
        bare_relative=False,
    )


def _resolve_common_import(
    value: str,
    *,
    from_path: str,
    all_paths: set[str],
    extensions: Sequence[str],
    metadata: dict[str, Any],
    resolver: str = "common",
    bare_relative: bool = False,
) -> tuple[str | None, str, dict[str, Any]]:
    bases: list[str] = []
    external = False
    reason = "import_not_resolved"
    if value.startswith(('.', '..')):
        bases.append(posixpath.normpath(posixpath.join(posixpath.dirname(from_path), value)))
        reason = "relative_path_not_found"
    elif value.startswith('/'):
        bases.append(value.strip('/'))
        reason = "absolute_path_not_found"
    elif bare_relative:
        bases.append(posixpath.normpath(posixpath.join(posixpath.dirname(from_path), value)))
        reason = "bare_relative_path_not_found"
    elif "/" in value:
        bases.append(value)
        reason = "project_path_not_found"
    else:
        external = True
    resolved, attempted, matches = _resolve_candidates(bases, all_paths, extensions)
    if len(matches) > 1:
        return _ambiguous_resolution(metadata, resolver=resolver, attempted_paths=attempted, matches=matches)
    if resolved:
        base_exact = _normalize_path(bases[0]) if bases else ""
        confidence = "exact" if resolved == base_exact else "heuristic"
        return _resolution_result(resolved, metadata, resolver=resolver, reason="resolved_existing_path", external=False, attempted_paths=attempted, confidence=confidence)
    return _resolution_result(None, metadata, resolver=resolver, reason=reason, external=external, attempted_paths=attempted, confidence="unresolved")


def _resolve_candidates(bases: Sequence[str], all_paths: set[str], extensions: Sequence[str]) -> tuple[str | None, list[str], list[str]]:
    attempted: list[str] = []
    for base in bases:
        normalized = _normalize_path(base)
        for candidate in [normalized, *[_normalize_path(f"{normalized}{extension}") for extension in extensions]]:
            if candidate not in attempted:
                attempted.append(candidate)
    matches = [candidate for candidate in attempted if candidate in all_paths]
    if len(matches) == 1:
        return matches[0], attempted[:8], matches
    return None, attempted[:8], matches


def _resolution_result(
    resolved: str | None,
    metadata: dict[str, Any],
    *,
    resolver: str,
    reason: str,
    external: bool,
    attempted_paths: Sequence[str],
    confidence: str,
) -> tuple[str | None, str, dict[str, Any]]:
    return resolved, confidence, {
        **metadata,
        "resolver": resolver,
        "reason": reason,
        "external": external,
        "attempted_paths": list(attempted_paths)[:8],
        "confidence": confidence,
    }


def _ambiguous_resolution(metadata: dict[str, Any], *, resolver: str, attempted_paths: Sequence[str], matches: Sequence[str]) -> tuple[str | None, str, dict[str, Any]]:
    return None, "unresolved", {
        **metadata,
        "resolver": resolver,
        "reason": "ambiguous_local_import",
        "external": False,
        "attempted_paths": list(attempted_paths)[:8],
        "confidence": "unresolved",
        "candidate_count": len(matches),
        "candidate_paths": list(matches)[:8],
    }


def _extra_import_values(text: str, language: str) -> list[str]:
    if language not in {"javascript", "typescript"}:
        return []
    values: list[str] = []
    for match in re.finditer(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
        value = match.group(1)
        if value not in values:
            values.append(value)
    return values[:20]


def _reference_edges_for(reference: str, *, file_node_id: str, from_path: str, symbol_index: dict[str, list[CodeGraphNode]]) -> list[CodeGraphEdge]:
    candidates = _symbol_candidates(reference, symbol_index)
    if len(candidates) == 1:
        target = candidates[0]
        return [CodeGraphEdge(
            id=make_edge_id("references", file_node_id, target.id, symbol=reference),
            kind="references",
            from_node_id=file_node_id,
            to_node_id=target.id,
            from_path=from_path,
            to_path=target.path,
            symbol=reference,
            confidence="heuristic",
            confidence_score=confidence_score_for("heuristic"),
            evidence=reference,
        )]
    metadata: dict[str, Any] = {"reference": reference}
    if candidates:
        metadata.update({
            "candidate_count": len(candidates),
            "candidate_paths": [node.path for node in candidates[:5]],
            "reason": "multiple_matching_symbol_definitions",
        })
    else:
        metadata["reason"] = "no_matching_symbol_definition"
    return [CodeGraphEdge(
        id=make_edge_id("unresolved_reference", file_node_id, None, symbol=reference),
        kind="unresolved_reference",
        from_node_id=file_node_id,
        from_path=from_path,
        symbol=reference,
        confidence="unresolved",
        confidence_score=confidence_score_for("unresolved"),
        evidence=reference,
        metadata=metadata,
    )]


def _build_symbol_index(nodes: list[CodeGraphNode]) -> dict[str, list[CodeGraphNode]]:
    index: dict[str, list[CodeGraphNode]] = {}
    for node in nodes:
        if node.kind != "symbol":
            continue
        for key in _symbol_keys(node.name):
            index.setdefault(key, []).append(node)
    return index


def _symbol_candidates(reference: str, symbol_index: dict[str, list[CodeGraphNode]]) -> list[CodeGraphNode]:
    seen: dict[str, CodeGraphNode] = {}
    for key in _symbol_keys(reference):
        for node in symbol_index.get(key, []):
            seen[node.id] = node
    return sorted(seen.values(), key=lambda node: (node.path, node.line_start or 0, node.name))


def _symbol_keys(value: str) -> set[str]:
    raw = str(value or '').strip()
    if not raw:
        return set()
    split = _CAMEL_SPLIT_RE.sub(" ", raw.replace("_", " ").replace("-", " "))
    compact = re.sub(r"[^A-Za-z0-9]+", "", raw).casefold()
    spaced = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", split)).strip().casefold()
    return {key for key in {compact, spaced} if key}


def _merge_question_requirements(question: str, requirements: Sequence[str] | None) -> str:
    parts = [question.strip()]
    parts.extend(str(item).strip() for item in requirements or [] if str(item).strip())
    return " ".join(part for part in parts if part)


def _dedupe_nodes(nodes: list[CodeGraphNode]) -> list[CodeGraphNode]:
    deduped: dict[str, CodeGraphNode] = {}
    for node in nodes:
        deduped.setdefault(node.id, node)
    return list(deduped.values())


def _dedupe_edges(edges: list[CodeGraphEdge]) -> list[CodeGraphEdge]:
    deduped: dict[str, CodeGraphEdge] = {}
    for edge in edges:
        deduped.setdefault(edge.id, edge)
    return list(deduped.values())


def _sort_nodes(nodes: list[CodeGraphNode]) -> list[CodeGraphNode]:
    return sorted(nodes, key=lambda node: (node.kind, node.path, node.line_start or 0, node.name))


def _sort_edges(edges: list[CodeGraphEdge]) -> list[CodeGraphEdge]:
    return sorted(edges, key=lambda edge: (edge.kind, edge.from_path or "", edge.to_path or "", edge.symbol or "", edge.line_start or 0, edge.id))


def _graph_diagnostics(facts: list[dict[str, Any]], nodes: list[CodeGraphNode], edges: list[CodeGraphEdge], *, max_files: int, token_budget: int) -> dict[str, Any]:
    edge_kinds = Counter(edge.kind for edge in edges)
    confidence_summary = Counter(edge.confidence for edge in edges)
    languages: list[str] = []
    for item in facts:
        language = item.get("language")
        if language and str(language) not in languages:
            languages.append(str(language))
    return {
        "status": "ok",
        "scanned_files": len(facts),
        "selected_files": len(facts),
        "selected_paths": [item.get("path") for item in facts if item.get("path")][:20],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "file_node_count": sum(1 for node in nodes if node.kind == "file"),
        "symbol_node_count": sum(1 for node in nodes if node.kind == "symbol"),
        "edge_kinds": dict(sorted(edge_kinds.items())),
        "confidence_summary": dict(sorted(confidence_summary.items())),
        "unresolved_import_count": edge_kinds.get("unresolved_import", 0) + edge_kinds.get("unresolved_export", 0),
        "unresolved_reference_count": edge_kinds.get("unresolved_reference", 0),
        "languages": languages[:20],
        "token_budget": token_budget,
        "token_estimate": sum(int(item.get("token_estimate") or 0) for item in facts),
        "max_files": max_files,
        "builder": "source_facts",
        "graph_scope": "selected_files",
        "limitations": [
            "not_call_graph",
            "name_based_reference_resolution",
            "regex_symbols_for_non_python",
        ],
    }


def _pubspec_name(root: Path) -> str | None:
    path = root / "pubspec.yaml"
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"^\s*name:\s*([A-Za-z0-9_\-]+)\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").strip("/")

__all__=['CodeGraphNode', 'CodeGraphEdge', 'CodeGraph', 'CodeGraphPath', 'build_project_code_graph', '_path_node_matches', '_connected_target_ids', '_path_adjacency', '_code_graph_path_from_ids', '_path_confidence', '_path_explanation', '_path_sort_text', 'make_file_node_id', 'make_symbol_node_id', 'make_edge_id', 'confidence_score_for', '_symbols_for_file', '_file_strings', '_context_query_terms', '_contains_term', '_normalize_match_text', '_resolve_import_to_path', '_resolve_dart_import', '_resolve_python_import', '_resolve_js_ts_import', '_resolve_common_import', '_resolve_candidates', '_resolution_result', '_ambiguous_resolution', '_extra_import_values', '_reference_edges_for', '_build_symbol_index', '_symbol_candidates', '_symbol_keys', '_merge_question_requirements', '_dedupe_nodes', '_dedupe_edges', '_sort_nodes', '_sort_edges', '_graph_diagnostics', '_pubspec_name', '_optional_int', '_normalize_path']
