"""Implementation shard 2 for patch_plan_context."""
from __future__ import annotations

from ._patch_plan_context_shared import *  # noqa: F401,F403

from ._patch_plan_context_part01 import _changed_file_candidate, _iter_source_files, _merge_duplicate_source_candidates, _ordered_terms, _read_text, _score_source_file, _term_variants, _to_snake_case, build_implementation_map, discover_dart_dependency_apis, discover_missing_symbols, discover_rejected_sources

def build_patch_plan_context(
    question: str,
    *,
    project_path: str | None = None,
    changed_files: list[str] | None = None,
    symbol_queries: list[str] | None = None,
    design_context: dict[str, Any] | None = None,
    include_dependency_source: bool = True,
    max_files: int | None = 12,
    max_snippets: int | None = 16,
    max_tokens: int | None = 2400,
    output_mode: str | None = "compact",
) -> dict[str, Any]:
    """Return patch-planning response shape with lightweight source discovery."""

    mode = output_mode if output_mode in {"compact", "debug", "full"} else "compact"
    relevant_files = discover_relevant_source_files(
        question,
        project_path=project_path,
        changed_files=changed_files,
        symbol_queries=symbol_queries,
        max_files=max_files or 12,
        max_snippets=max_snippets or 16,
    )
    graph_diagnostics: dict[str, Any] = {"graph_used": False, "fallback_reason": None}
    if project_path:
        root = Path(project_path).expanduser().resolve()
        graph_requirements = [*list(symbol_queries or []), *list(changed_files or [])]
        graph_hints, graph_diagnostics = _graph_relevant_file_hints(
            root,
            question=question,
            requirements=graph_requirements,
            changed_files=changed_files,
            max_files=6,
            max_depth=1,
        )
        relevant_files = _merge_graph_hints_into_relevant_files(
            relevant_files,
            graph_hints,
            max_files=max_files or 12,
            max_snippets=max_snippets or 16,
        )
    dependency_apis, dependency_warnings = discover_dart_dependency_apis(
        question,
        project_path=project_path,
        symbol_queries=symbol_queries,
        include_dependency_source=include_dependency_source,
    )
    missing_symbols = discover_missing_symbols(
        question,
        project_path=project_path,
        symbol_queries=symbol_queries,
        searched_dependency=bool(dependency_apis),
        dependency_apis=dependency_apis,
    )
    implementation_map = build_implementation_map(
        question,
        project_path=project_path,
        relevant_files=relevant_files,
        existing_apis=dependency_apis,
        missing_symbols=missing_symbols,
        design_context=design_context,
    )
    rejected_sources = discover_rejected_sources(question, project_path=project_path, symbol_queries=symbol_queries)
    warnings = [_PATCH_PLAN_LIMITED_WARNING] if project_path else [_PATCH_PLAN_NOT_IMPLEMENTED_WARNING]
    warnings.extend(dependency_warnings)
    warnings.extend(implementation_map["warnings"])
    payload = {
        "schema_version": PATCH_PLAN_CONTEXT_SCHEMA_VERSION,
        "tool": PATCH_PLAN_CONTEXT_TOOL,
        "status": "partial",
        "reason_code": None,
        "answer_available": bool(relevant_files or dependency_apis or missing_symbols),
        "answer_completeness": "partial_navigational",
        "task": {
            "title": question,
            "project": project_path,
        },
        "current_behavior": implementation_map["current_behavior"],
        "relevant_files": relevant_files,
        "existing_apis": dependency_apis,
        "missing_symbols": missing_symbols,
        "design_context": design_context,
        "minimal_patch_path": implementation_map["minimal_patch_path"],
        "risks_and_constraints": implementation_map["risks_and_constraints"],
        "verification": implementation_map["verification"],
        "evidence": [],
        "rejected_sources": rejected_sources,
        "warnings": warnings,
        "next_actions": implementation_map["next_actions"],
        "token_estimate": 0,
        "output_mode": mode,
    }
    if mode != "compact":
        payload["diagnostics"] = {"code_graph": graph_diagnostics}
    payload["token_estimate"] = _estimate_tokens(payload)
    if mode == "compact":
        payload = _enforce_patch_plan_budget(payload, max_tokens=max_tokens or 2400)
    return payload


class PatchPlanContextService:
    def __init__(self, service: Any | None = None):
        self.service = service

    def get_patch_plan_context(self, question: str, **kwargs: Any) -> dict[str, Any]:
        return build_patch_plan_context(question, **kwargs)


def discover_relevant_source_files(
    question: str,
    *,
    project_path: str | None,
    changed_files: list[str] | None = None,
    symbol_queries: list[str] | None = None,
    max_files: int = 12,
    max_snippets: int = 16,
) -> list[dict[str, Any]]:
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is None or not root.exists() or not root.is_dir():
        return []

    ordered_terms = _ordered_terms(question, symbol_queries or [])
    if not ordered_terms:
        return []
    variants_by_term = {term: _term_variants(term) for term in ordered_terms}

    candidates: list[dict[str, Any]] = []
    for path in _iter_source_files(root):
        rel_path = path.relative_to(root).as_posix()
        text = _read_text(path)
        if text is None:
            continue
        candidate = _score_source_file(rel_path, text, ordered_terms, variants_by_term)
        if candidate is not None:
            candidates.append(candidate)

    for changed_index, changed_file in enumerate(changed_files or []):
        candidate = _changed_file_candidate(root, changed_file)
        if candidate is not None:
            candidate["_changed_file_index"] = changed_index
            candidates.append(candidate)

    candidates = _merge_duplicate_source_candidates(candidates)
    candidates.sort(key=lambda item: (-item["_score"], item.get("_changed_file_index", 10_000), item["_first_term_index"], item["file"]))
    public: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for item in candidates:
        if item["file"] in seen_files:
            continue
        seen_files.add(item["file"])
        public.append(_public_relevant_file(item))
        if len(public) >= max(1, max_files):
            break
    return _cap_relevant_file_refs(public, max_snippets=max_snippets)


def _graph_relevant_file_hints(
    root: Path,
    *,
    question: str,
    requirements: Sequence[str] | None = None,
    changed_files: Sequence[str] | None = None,
    max_files: int = 6,
    max_depth: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "graph_used": False,
        "fallback_reason": None,
        "seed_files": [],
        "selected_graph_files": [],
        "edge_kinds": [],
        "max_depth": max_depth,
        "max_files": max_files,
        "limitations": ["not_call_graph", "depth_limited"],
    }
    if not root.exists() or not root.is_dir():
        diagnostics["fallback_reason"] = "invalid_root"
        return [], diagnostics
    try:
        graph = build_project_code_graph(
            root,
            question=question,
            requirements=requirements,
            max_files=24,
            token_budget=3500,
        )
    except Exception as exc:
        diagnostics["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        return [], diagnostics

    file_nodes = {node.path: node for node in graph.nodes if node.kind == "file"}
    if not file_nodes:
        diagnostics["fallback_reason"] = "empty_graph"
        return [], diagnostics
    diagnostics["graph"] = code_graph_diagnostics(graph)

    terms = _graph_query_terms(question, requirements or [])
    changed = {str(path).replace("\\", "/").strip("/") for path in changed_files or [] if str(path).strip()}
    hints: dict[str, dict[str, Any]] = {}

    def add_hint(path: str, boost: float, reason: str, edge_kinds: Sequence[str] = (), confidence: str = "heuristic", linked_paths: Sequence[str] = ()) -> None:
        if not path or path not in file_nodes:
            return
        item = hints.setdefault(path, {
            "path": path,
            "score_boost": 0.0,
            "reason": "",
            "edge_kinds": [],
            "confidence": confidence,
            "linked_paths": [],
        })
        item["score_boost"] = float(item["score_boost"]) + boost
        if reason and reason not in item["reason"]:
            item["reason"] = f"{item['reason']}; {reason}" if item["reason"] else reason
        for kind in edge_kinds:
            if kind not in item["edge_kinds"]:
                item["edge_kinds"].append(kind)
        for linked in linked_paths:
            if linked and linked not in item["linked_paths"]:
                item["linked_paths"].append(linked)
        if _confidence_rank(confidence) > _confidence_rank(str(item.get("confidence") or "heuristic")):
            item["confidence"] = confidence

    symbols_by_path: dict[str, list[Any]] = {}
    for node in graph.nodes:
        if node.kind == "symbol":
            symbols_by_path.setdefault(node.path, []).append(node)

    for path, node in file_nodes.items():
        if path in changed:
            add_hint(path, 4, "code_graph: changed_file seed; confidence=exact", confidence="exact")
        if _graph_text_matches(path, terms):
            add_hint(path, 5, "code_graph: exact path match; confidence=heuristic", confidence="heuristic")
        strings = [str(value) for key in ("string_literals", "status_like_tokens") for value in node.metadata.get(key) or []]
        if any(_graph_text_matches(value, terms) for value in strings):
            add_hint(path, 5, "code_graph: exact string/status match; confidence=heuristic", confidence="heuristic")
        if any(_graph_text_matches(symbol.name, terms) for symbol in symbols_by_path.get(path, [])):
            confidence = "parser" if node.language == "python" else "regex"
            add_hint(path, 5, f"code_graph: exact symbol match; confidence={confidence}", confidence=confidence)

    for edge in graph.edges:
        if edge.kind in {"references", "unresolved_reference"} and edge.symbol and _graph_text_matches(edge.symbol, terms):
            if edge.kind == "references" and edge.from_path:
                add_hint(edge.from_path, 3, f"code_graph: reference edge matched `{edge.symbol}`; confidence={edge.confidence}", [edge.kind], edge.confidence, [edge.to_path] if edge.to_path else [])
            elif edge.from_path:
                add_hint(edge.from_path, 0.5, f"code_graph: unresolved reference search hint `{edge.symbol}`; confidence=unresolved", [edge.kind], "unresolved")
        if edge.kind in {"imports", "exports"} and edge.from_path and edge.to_path:
            if _graph_text_matches(edge.to_path, terms) or _graph_text_matches(edge.symbol or "", terms):
                add_hint(edge.from_path, 2, f"code_graph: import/export neighbor matched task terms; confidence={edge.confidence}", [edge.kind], edge.confidence, [edge.to_path])
        if edge.kind in {"unresolved_import", "unresolved_export"} and edge.from_path and _graph_text_matches(edge.evidence or edge.symbol or "", terms):
            add_hint(edge.from_path, 0.5, "code_graph: unresolved import/export search hint; confidence=unresolved", [edge.kind], "unresolved")

    seed_files = sorted(
        path for path, item in hints.items()
        if float(item.get("score_boost") or 0) >= 3
        and "import/export neighbor" not in str(item.get("reason") or "")
    )
    diagnostics["seed_files"] = seed_files
    if max_depth > 0:
        for seed in list(seed_files):
            for edge in graph.edges:
                if edge.kind not in {"imports", "exports", "references"}:
                    continue
                if edge.from_path == seed and edge.to_path in file_nodes:
                    add_hint(edge.to_path, 2, f"code_graph: linked by local import/reference to task-relevant file; confidence={edge.confidence}", [edge.kind], edge.confidence, [seed])
                elif edge.to_path == seed and edge.from_path in file_nodes:
                    add_hint(edge.from_path, 2, f"code_graph: linked by local import/reference to task-relevant file; confidence={edge.confidence}", [edge.kind], edge.confidence, [seed])

    selected = sorted(hints.values(), key=lambda item: (-float(item["score_boost"]), item["path"]))[: max(1, max_files)]
    diagnostics["graph_used"] = True
    diagnostics["selected_graph_files"] = [item["path"] for item in selected]
    diagnostics["edge_kinds"] = sorted({kind for item in selected for kind in item.get("edge_kinds", [])})
    return selected, diagnostics


def _merge_graph_hints_into_relevant_files(
    relevant_files: list[dict[str, Any]],
    graph_hints: list[dict[str, Any]],
    *,
    max_files: int,
    max_snippets: int,
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in relevant_files]
    by_file = {item["file"]: item for item in merged}
    for hint in graph_hints[:6]:
        path = str(hint.get("path") or "")
        if not path:
            continue
        reason = str(hint.get("reason") or "code_graph: linked by local import/reference to task-relevant file; confidence=heuristic")
        if path in by_file:
            item = by_file[path]
            if "code_graph" not in str(item.get("why") or ""):
                item["why"] = f"{item.get('why') or 'Relevant source file found.'}; {reason}"
            item["graph_hint"] = hint
            continue
        item = {
            "file": path,
            "why": reason,
            "action": "read",
            "symbols": [],
            "refs": [],
            "graph_hint": hint,
        }
        merged.append(item)
        by_file[path] = item
    return _cap_relevant_file_refs(merged[: max(1, max_files)], max_snippets=max_snippets)


def _graph_query_terms(question: str, requirements: Sequence[str]) -> set[str]:
    terms: set[str] = set()
    generic = {"app", "lib", "src", "dart", "file", "files", "service", "services", "screen", "screens"}
    for raw in [question, *requirements]:
        for word in _WORD_RE.findall(str(raw)):
            if word.casefold() in generic:
                continue
            for variant in _term_variants(word):
                normalized = _graph_normalize(variant)
                if len(normalized) >= 3 and normalized not in generic:
                    terms.add(normalized)
        for quoted in re.finditer(r"[\"'“”«»](.*?)[\"'“”«»]", str(raw)):
            value = quoted.group(1).strip()
            if value:
                terms.add(_graph_normalize(value))
    return {term for term in terms if term}


def _graph_text_matches(value: str, terms: set[str]) -> bool:
    if not terms:
        return False
    normalized = _graph_normalize(value)
    compact = normalized.replace(" ", "")
    return any(term in normalized or term in compact for term in terms)


def _graph_normalize(value: str) -> str:
    text = _to_snake_case(str(value).replace("/", "_").replace("-", "_").replace(".", "_"))
    text = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _confidence_rank(confidence: str) -> int:
    return {"unresolved": 0, "heuristic": 1, "regex": 2, "parser": 3, "exact": 4}.get(confidence, 1)


def _cap_relevant_file_refs(items: list[dict[str, Any]], *, max_snippets: int) -> list[dict[str, Any]]:
    remaining = max(1, max_snippets)
    capped: list[dict[str, Any]] = []
    for item in items:
        refs = item.get("refs") or []
        take = min(len(refs), max(1, remaining)) if remaining > 0 else 0
        capped_item = dict(item)
        capped_item["refs"] = refs[:take]
        capped.append(capped_item)
        remaining -= take
    return capped


def _estimate_tokens(payload: dict[str, Any]) -> int:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return max(1, len(encoded) // 4)


def _enforce_patch_plan_budget(payload: dict[str, Any], *, max_tokens: int) -> dict[str, Any]:
    max_bytes = max(800, max_tokens * 4)
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= max_bytes:
        return payload
    compact = dict(payload)
    for key, limit in (("relevant_files", 8), ("current_behavior", 5), ("existing_apis", 8), ("minimal_patch_path", 3), ("rejected_sources", 3)):
        value = compact.get(key)
        if isinstance(value, list):
            compact[key] = value[:limit]
    warnings = list(compact.get("warnings") or [])
    warnings.append("Patch planning output was compacted to stay within max_tokens budget; retry with output_mode='debug' or higher max_tokens for more context.")
    compact["warnings"] = warnings
    compact["token_estimate"] = _estimate_tokens(compact)
    return compact


def _public_relevant_file(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": item["file"],
        "why": item["why"],
        "action": item["action"],
        "symbols": item["symbols"],
        "refs": item["refs"],
    }

__all__=['build_patch_plan_context', 'PatchPlanContextService', 'discover_relevant_source_files', '_graph_relevant_file_hints', '_merge_graph_hints_into_relevant_files', '_graph_query_terms', '_graph_text_matches', '_graph_normalize', '_confidence_rank', '_cap_relevant_file_refs', '_estimate_tokens', '_enforce_patch_plan_budget', '_public_relevant_file']
