"""Navigation hints and preparation actions for context recovery."""
from __future__ import annotations

from typing import Any


def _patch_navigation_hints(
    packet: dict[str, Any], payload: dict[str, Any],
) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    source_rows = packet.get("source_of_truth")
    candidates = source_rows if isinstance(source_rows, list) and source_rows else payload.get("context_pack")
    for row in candidates if isinstance(candidates, list) else []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or row.get("source") or "").strip()[:300]
        if path.casefold().endswith((".md", ".mdx", ".rst", ".txt", ".adoc")) and path not in paths:
            paths.append(path)
        if len(paths) == 5:
            break

    symbols: list[str] = []
    target_surface = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    for row in target_surface.get("symbols") if isinstance(target_surface.get("symbols"), list) else []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("name") or "").strip()[:160]
        if symbol and symbol not in symbols:
            symbols.append(symbol)
        if len(symbols) == 5:
            break
    return paths, symbols


def _replace_network_retries_with_prepare_actions(payload: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Keep the public retrieval tool from suggesting another mutating retry."""

    def rewrite(action: Any) -> Any:
        if not isinstance(action, dict):
            return action
        arguments = dict(action.get("arguments_patch") or {})
        if action.get("tool") == "prepare_docs":
            # Network approval is a user decision, not a callable MCP field.
            # The returned lifecycle action must pass its own public validator.
            arguments.pop("allow_network", None)
            if arguments.get("action") == "prefetch_library_docs" and not arguments.get("question"):
                arguments["question"] = request.get("question")
            prepared = {**action, "arguments_patch": arguments}
            if payload.get("requires_confirmation") and "requires_confirmation" not in prepared:
                prepared["requires_confirmation"] = True
            if payload.get("confirmation_reason") and not prepared.get("confirmation_reason"):
                prepared["confirmation_reason"] = payload["confirmation_reason"]
            return prepared
        if action.get("tool") != "get_docs_context" or not arguments.get("allow_network"):
            return action
        if request.get("mode") == "project":
            return None
        library = request.get("library")
        if library:
            patch = {
                "action": "prefetch_library_docs",
                "library": library,
                "question": request.get("question"),
                **{
                    key: request[key]
                    for key in ("ecosystem", "version", "source_type", "docs_url")
                    if request.get(key) is not None
                },
            }
        elif request.get("project_path"):
            patch = {
                "action": "prefetch_project_dependency_docs",
                "project_path": request["project_path"],
            }
        else:
            return action
        return {
            **action,
            "type": "prepare_docs",
            "tool": "prepare_docs",
            "arguments_patch": patch,
            **({"requires_confirmation": True} if payload.get("requires_confirmation") else {}),
            **({"confirmation_reason": payload["confirmation_reason"]} if payload.get("confirmation_reason") else {}),
        }

    updated = dict(payload)
    actions = []
    for action in updated.get("next_actions") or []:
        candidate = rewrite(action)
        if candidate is not None and candidate not in actions:
            actions.append(candidate)
    primary = rewrite(updated.get("next_action"))
    if primary is not None and primary not in actions:
        actions.insert(0, primary)
    updated["next_actions"] = actions
    updated["next_action"] = primary or (actions[0] if actions else None)
    if isinstance(updated.get("lanes"), dict):
        updated["lanes"] = {
            name: {**lane, "next_action": rewrite(lane.get("next_action"))}
            if isinstance(lane, dict) else lane
            for name, lane in updated["lanes"].items()
        }
    if isinstance(updated.get("arguments_patch"), dict) and updated["arguments_patch"].get("allow_network"):
        updated["arguments_patch"] = dict(updated["next_action"].get("arguments_patch") or {}) if updated.get("next_action") else {}
    return updated
