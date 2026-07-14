from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval.task_level.schemas import TaskSpec


@dataclass(frozen=True)
class DocAtlasUtilization:
    available: bool = False
    harness_calls: int = 0
    agent_calls: int = 0
    context_retrieved: bool = False
    context_injected: bool = False
    context_used: bool = False
    context_used_confidence: str = "none"
    used_symbols: list[str] = field(default_factory=list)
    used_sources: list[str] = field(default_factory=list)
    used_project_constraints: list[str] = field(default_factory=list)
    used_version_info: list[str] = field(default_factory=list)
    docatlas_retrieval_status: str | None = None
    vector_indexing_timed_out: bool = False
    fallback_used: bool = False
    fallback_source: str | None = None
    docatlas_tool_success: bool = False
    docatlas_fallback_success: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "harness_calls": self.harness_calls,
            "agent_calls": self.agent_calls,
            "context_retrieved": self.context_retrieved,
            "context_injected": self.context_injected,
            "context_used": self.context_used,
            "context_used_confidence": self.context_used_confidence,
            "used_symbols": self.used_symbols,
            "used_sources": self.used_sources,
            "used_project_constraints": self.used_project_constraints,
            "used_version_info": self.used_version_info,
            "docatlas_retrieval_status": self.docatlas_retrieval_status,
            "vector_indexing_timed_out": self.vector_indexing_timed_out,
            "fallback_used": self.fallback_used,
            "fallback_source": self.fallback_source,
            "docatlas_tool_success": self.docatlas_tool_success,
            "docatlas_fallback_success": self.docatlas_fallback_success,
        }


def evaluate_docatlas_utilization(
    *,
    task: TaskSpec,
    condition_id: str,
    run_output_dir: Path,
    patch_path: Path,
    trajectory_path: Path | None,
    agent_docatlas_calls: int,
) -> DocAtlasUtilization:
    available = condition_id.startswith("docatlas_")
    response_path = run_output_dir / "docatlas_response.json"
    packet_path = run_output_dir / "action_packet.json"
    injected_path = run_output_dir / "injected_context.md"
    sources_path = run_output_dir / "context_sources.json"
    injection_path = run_output_dir / "docatlas_context_injection.json"
    context_retrieved = response_path.exists() or packet_path.exists()
    context_injected = injected_path.exists() or packet_path.exists()
    delivery_metrics = _load_json(run_output_dir / "isolated_delivery_metrics.json") or _load_json(run_output_dir / "bounded_direct_metrics.json")
    harness_calls = int(delivery_metrics.get("retrieval_calls") or (1 if context_retrieved else 0))
    injection = _load_json(injection_path)
    retrieval_status = injection.get("docatlas_retrieval_status") or injection.get("status")
    fallback_used = bool(injection.get("fallback_used"))
    vector_timed_out = bool(injection.get("vector_indexing_timed_out"))
    fallback_source = str(injection.get("fallback_source")) if injection.get("fallback_source") else None
    if not available and harness_calls == 0 and agent_docatlas_calls == 0:
        return DocAtlasUtilization(available=False)

    patch_text = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
    trajectory_text = trajectory_path.read_text(encoding="utf-8") if trajectory_path and trajectory_path.exists() else ""
    context_text = ""
    if injected_path.exists():
        context_text += injected_path.read_text(encoding="utf-8")
    if response_path.exists():
        context_text += "\n" + response_path.read_text(encoding="utf-8")[:12000]
    if packet_path.exists():
        context_text += "\n" + packet_path.read_text(encoding="utf-8")
    if agent_docatlas_calls and trajectory_path and trajectory_path.exists():
        context_text += "\n" + trajectory_path.read_text(encoding="utf-8")[:20000]
    if not context_text.strip():
        return DocAtlasUtilization(
            available=available,
            agent_calls=agent_docatlas_calls,
            harness_calls=harness_calls,
            docatlas_retrieval_status=retrieval_status,
            vector_indexing_timed_out=vector_timed_out,
            fallback_used=fallback_used,
            fallback_source=fallback_source,
            docatlas_tool_success=agent_docatlas_calls > 0,
            docatlas_fallback_success=fallback_used,
        )

    candidate_symbols = _candidate_symbols(task, context_text)
    used_symbols = sorted(symbol for symbol in candidate_symbols if symbol and symbol in patch_text)
    used_sources = _used_sources(sources_path, trajectory_text)
    used_project_constraints = _used_project_constraints(task, patch_text, context_text)
    used_version_info = _used_version_info(task, patch_text, context_text, trajectory_text)

    confidence = "none"
    if used_symbols and (used_sources or used_project_constraints or used_version_info):
        confidence = "high"
    elif used_symbols or used_project_constraints or used_version_info:
        confidence = "medium"
    elif used_sources:
        confidence = "low"

    return DocAtlasUtilization(
        available=available,
        harness_calls=harness_calls,
        agent_calls=agent_docatlas_calls,
        context_retrieved=context_retrieved,
        context_injected=context_injected,
        context_used=confidence != "none",
        context_used_confidence=confidence,
        used_symbols=used_symbols,
        used_sources=used_sources,
        used_project_constraints=used_project_constraints,
        used_version_info=used_version_info,
        docatlas_retrieval_status=retrieval_status,
        vector_indexing_timed_out=vector_timed_out,
        fallback_used=fallback_used,
        fallback_source=fallback_source,
        docatlas_tool_success=agent_docatlas_calls > 0 or (context_retrieved and not fallback_used),
        docatlas_fallback_success=fallback_used and confidence != "none",
    )


def _candidate_symbols(task: TaskSpec, context_text: str) -> set[str]:
    symbols = {item.split(":")[-1] for item in task.expected_symbols if item.split(":")[-1] in context_text}
    for token in ("Annotated", "Depends", "BackgroundTasks", "HTTPException", "Header", "require_admin", "error_envelope", "Permission.notification", "Permission.locationAlways", "PermissionInfo", "isCritical"):
        if token in context_text:
            symbols.add(token)
    return symbols


def _used_sources(sources_path: Path, trajectory_text: str) -> list[str]:
    if not sources_path.exists():
        return []
    try:
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    used: list[str] = []
    for source in sources if isinstance(sources, list) else []:
        path = str(source.get("path") or source.get("url") or source.get("source") or "")
        if path and path in trajectory_text:
            used.append(path)
    return sorted(set(used))


def _used_project_constraints(task: TaskSpec, patch_text: str, context_text: str) -> list[str]:
    constraints: list[str] = []
    if "require_admin" in context_text and "require_admin" in patch_text:
        constraints.append("shared require_admin dependency")
    if "error envelope" in context_text.lower() and "error_envelope" in patch_text:
        constraints.append("documented error envelope")
    for doc_path in task.expected_project_docs:
        if doc_path in context_text and doc_path in patch_text:
            constraints.append(f"referenced {doc_path}")
    return sorted(set(constraints))


def _used_version_info(task: TaskSpec, patch_text: str, context_text: str, trajectory_text: str) -> list[str]:
    used: list[str] = []
    combined = f"{patch_text}\n{trajectory_text}"
    for dep in task.dependencies:
        if dep.version in context_text and dep.version in combined:
            used.append(f"{dep.name}=={dep.version}")
    return used


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
