from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.task_level.context.patch_constraints import PatchConstraintPacket, packet_from_json


def load_patch_constraint_packet(path: Path) -> PatchConstraintPacket | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return packet_from_json(data) if isinstance(data, dict) else None


def evaluate_patch_constraint_usage(packet: PatchConstraintPacket | None, patch_path: Path, trajectory_path: Path | None = None) -> dict[str, Any]:
    if packet is None:
        return {
            "constraint_count": 0,
            "constraint_used": False,
            "constraint_matches": [],
            "constraint_packet_tokens": None,
        }
    patch_text = patch_path.read_text(encoding="utf-8", errors="replace") if patch_path.exists() else ""
    trajectory_text = trajectory_path.read_text(encoding="utf-8", errors="replace") if trajectory_path and trajectory_path.exists() else ""
    combined = f"{patch_text}\n{trajectory_text}"
    matches: list[dict[str, Any]] = []
    for constraint in packet.constraints:
        symbols = [symbol for symbol in constraint.symbols if symbol and symbol in combined]
        files = [file for file in constraint.files if file and file in combined]
        if symbols or files:
            matches.append({
                "constraint_id": constraint.id,
                "symbols": symbols,
                "files": files,
            })
    return {
        "constraint_count": len(packet.constraints),
        "constraint_used": bool(matches),
        "constraint_matches": matches,
        "constraint_packet_tokens": packet.token_estimate,
    }
