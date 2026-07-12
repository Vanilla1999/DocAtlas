from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from docmancer._version import __version__


_POLICY_PATH = Path(__file__).with_name("support_surfaces.json")
_ALLOWED_TIERS = {"core", "advanced-supported", "maintenance-only", "deprecated", "internal"}
_REQUIRED_NON_CORE = {
    "owner",
    "docs",
    "test_tier",
    "network_dependencies",
    "compatibility",
    "removal_rule",
    "failure_budget",
}

# Registration boundary for services that are intentionally shipped as
# supported product surfaces. Adding a new public service requires updating
# this registry; the policy test then requires a matching classified entry.
SHIPPED_SERVICE_SURFACE_IDS = frozenset({
    "service:browser-fetcher",
    "service:crawl4ai-fetcher",
    "service:mcp-packs-runtime",
    "service:qdrant-store",
    "service:sqlite-vec-store",
    "service:uspto-ingestion",
    "service:web-fetch-pipeline",
})


def _version_tuple(value: str) -> tuple[int, ...] | None:
    if not re.fullmatch(r"\d+(?:\.\d+)+", value):
        return None
    return tuple(int(part) for part in value.split("."))


def load_support_policy(path: str | Path | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path is not None else _POLICY_PATH
    return json.loads(policy_path.read_text(encoding="utf-8"))


def validate_support_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    surfaces = policy.get("surfaces")
    if not isinstance(surfaces, list):
        return ["surfaces must be a list"]
    seen: set[str] = set()
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            errors.append(f"surfaces[{index}] must be an object")
            continue
        surface_id = surface.get("id")
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"surfaces[{index}].id must be a non-empty string")
            continue
        if surface_id in seen:
            errors.append(f"duplicate surface id: {surface_id}")
        seen.add(surface_id)
        tier = surface.get("tier")
        if tier not in _ALLOWED_TIERS:
            errors.append(f"{surface_id}: invalid tier {tier!r}")
        if not isinstance(surface.get("kind"), str) or not surface.get("kind"):
            errors.append(f"{surface_id}: kind is required")
        if tier != "core":
            missing = sorted(_REQUIRED_NON_CORE - surface.keys())
            if missing:
                errors.append(f"{surface_id}: missing {', '.join(missing)}")
        if tier == "deprecated":
            deprecation = surface.get("deprecation")
            if not isinstance(deprecation, dict) or not deprecation.get("deadline") or not deprecation.get("resolution"):
                errors.append(f"{surface_id}: deprecated surfaces require a bounded resolution")
                continue
            deadline = _version_tuple(str(deprecation["deadline"]))
            current = _version_tuple(__version__)
            if deadline is None:
                errors.append(f"{surface_id}: deadline must be a dotted release version")
            elif current is not None and deadline <= current:
                errors.append(f"{surface_id}: deadline {deprecation['deadline']} has expired")
    return errors


def label_cli_commands(root: Any, policy: dict[str, Any] | None = None) -> None:
    policy = deepcopy(policy or load_support_policy())
    tiers = {
        item["id"]: item["tier"]
        for item in policy["surfaces"]
        if item.get("kind") == "cli"
    }

    def label(group: Any, prefix: str = "cli") -> None:
        for name, command in getattr(group, "commands", {}).items():
            surface_id = f"{prefix}:{name}" if prefix == "cli" else f"{prefix}/{name}"
            tier = tiers.get(surface_id)
            if tier:
                marker = f"[{tier}]"
                text = command.help or command.short_help or ""
                if not text.startswith(marker):
                    command.help = f"{marker} {text}".rstrip()
                    command.short_help = f"{marker} {command.short_help or text}".rstrip()
            if getattr(command, "commands", None):
                label(command, surface_id)

    label(root)
