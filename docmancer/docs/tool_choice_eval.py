"""Opt-in evaluation harness for the installed three-tool agent contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


MODEL_ADAPTER_NAME = "openai-compatible-low-cost"
REPEATS = 3
THRESHOLDS = {
    "first_tool_accuracy": 0.95,
    "unnecessary_prepare_or_status_rate": 0.05,
    "legacy_tool_hallucination_rate": 0.0,
    "next_action_copy_accuracy": 0.95,
    "original_question_retry_rate": 0.95,
}


@dataclass(frozen=True)
class ToolChoiceScenario:
    scenario_id: str
    prompt: str
    expected_first_tool: str | None
    expected_next_action: dict[str, Any] | None = None
    expected_retry_question: str | None = None
    messages: tuple[dict[str, str], ...] | None = None


class LowCostModelAdapter(Protocol):
    name: str
    model_version: str

    def choose_tool(self, *, guidance: str, tool_schemas: list[dict[str, Any]], scenario: ToolChoiceScenario) -> dict[str, Any]: ...


@dataclass
class OpenAICompatibleLowCostAdapter:
    """Named adapter shell; callers provide their approved low-cost completion client."""

    model_version: str
    completion: Callable[[dict[str, Any]], dict[str, Any]]
    name: str = MODEL_ADAPTER_NAME

    def choose_tool(self, *, guidance: str, tool_schemas: list[dict[str, Any]], scenario: ToolChoiceScenario) -> dict[str, Any]:
        return self.completion({"guidance": guidance, "tools": tool_schemas, "scenario": asdict(scenario)})


_SCENARIO_ROWS: tuple[tuple[Any, ...], ...] = (
    ("project-present", "How does this repository authenticate requests?", "get_docs_context"),
    ("project-missing", "Explain this project's architecture; its docs are not indexed.", "get_docs_context"),
    ("project-stale", "What does the current ADR say about caching?", "get_docs_context"),
    ("library-present", "How do I use FastAPI Depends?", "get_docs_context"),
    ("library-missing", "Show Kotlin coroutine launch usage.", "get_docs_context"),
    ("exact-library", "How does go_router 16.2.0 redirect?", "get_docs_context"),
    ("job-poll", "What is the status of job job-123?", "docs_status"),
    ("index-health", "Is the documentation index stale?", "docs_status"),
    ("implementation-only", "Where is request parsing implemented in this repo?", None),
    ("network-confirmation", "Fetch external docs after I approve network access.", "prepare_docs"),
    ("explicit-sync", "Sync the project's documentation now.", "prepare_docs"),
    ("invalid-payload", "Prepare Kotlin docs with an invalid field.", "prepare_docs"),
    ("unrelated", "Write a haiku about rain.", None),
    ("mixed-question", "How does this project use Riverpod providers?", "get_docs_context"),
    ("missing-action", "The docs response says to prefetch Kotlin 1.8.1; follow it.", "prepare_docs", {"action": "prefetch_library_docs", "library": "kotlin", "version": "1.8.1"}),
    (
        "retry-question",
        "Preparation succeeded. Continue the documentation workflow.",
        "get_docs_context",
        None,
        "Show Kotlin coroutine launch usage.",
        (
            {"role": "user", "content": "Show Kotlin coroutine launch usage."},
            {"role": "assistant", "content": "The required documentation preparation was started."},
            {"role": "user", "content": "Preparation succeeded. Continue the documentation workflow."},
        ),
    ),
    ("project-code-boundary", "Which source file implements the current retry loop?", None),
    ("dependency-version", "What API does the locked Flutter dependency expose?", "get_docs_context"),
    ("refresh-request", "Refresh the indexed library documentation.", "prepare_docs"),
    ("job-list", "List running documentation jobs.", "docs_status"),
)
SCENARIOS = tuple(ToolChoiceScenario(*row) for row in _SCENARIO_ROWS)  # type: ignore[arg-type]


def public_tool_schemas() -> list[dict[str, Any]]:
    """Load the real three-tool MCP surface used by the server."""
    from docmancer.mcp.docs_server import PUBLIC_TOOL_NAMES, TOOLS

    return [tool for tool in TOOLS if tool["name"] in PUBLIC_TOOL_NAMES]


def installed_guidance() -> str:
    """Render the same canonical guidance used by installed skill files."""
    from docmancer.cli.commands import _get_template_content

    return _get_template_content("skill.md")


def _schema_version(tool_schemas: list[dict[str, Any]]) -> str:
    encoded = json.dumps(tool_schemas, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()[:16]}"


def evaluate_tool_choice(adapter: LowCostModelAdapter, *, guidance: str, tool_schemas: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the frozen scenario set; network/model access is supplied by the caller."""
    if not guidance.strip():
        raise ValueError("installed guidance must not be empty")
    actual_names = {tool.get("name") for tool in tool_schemas}
    if actual_names != {"get_docs_context", "prepare_docs", "docs_status"}:
        raise ValueError("tool_schemas must contain the actual three public Docs MCP tools")
    results: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        for repeat in range(1, REPEATS + 1):
            response = dict(adapter.choose_tool(guidance=guidance, tool_schemas=tool_schemas, scenario=scenario) or {})
            tool = response.get("tool")
            results.append({
                "scenario_id": scenario.scenario_id,
                "repeat": repeat,
                "expected_tool": scenario.expected_first_tool,
                "tool": tool,
                "first_tool_correct": tool == scenario.expected_first_tool,
                "legacy_tool_hallucinated": bool(tool and tool not in {"get_docs_context", "prepare_docs", "docs_status"}),
                "unnecessary_prepare_or_status": scenario.expected_first_tool not in {"prepare_docs", "docs_status"} and tool in {"prepare_docs", "docs_status"},
                "next_action_correct": response.get("arguments") == scenario.expected_next_action if scenario.expected_next_action else None,
                "original_question_retried": (
                    response.get("arguments", {}).get("question") == scenario.expected_retry_question
                    if scenario.expected_retry_question is not None
                    else None
                ),
            })
    total = len(results)
    first_tool_accuracy = sum(item["first_tool_correct"] for item in results) / total
    legacy_rate = sum(item["legacy_tool_hallucinated"] for item in results) / total
    unnecessary_rate = sum(item["unnecessary_prepare_or_status"] for item in results) / total
    copied_actions = [item["next_action_correct"] for item in results if item["next_action_correct"] is not None]
    retried_questions = [item["original_question_retried"] for item in results if item["original_question_retried"] is not None]
    metrics = {
        "first_tool_accuracy": first_tool_accuracy,
        "unnecessary_prepare_or_status_rate": unnecessary_rate,
        "legacy_tool_hallucination_rate": legacy_rate,
        "next_action_copy_accuracy": sum(copied_actions) / len(copied_actions) if copied_actions else 0.0,
        "original_question_retry_rate": sum(retried_questions) / len(retried_questions) if retried_questions else 0.0,
    }
    passed = (
        metrics["first_tool_accuracy"] >= THRESHOLDS["first_tool_accuracy"]
        and metrics["unnecessary_prepare_or_status_rate"] <= THRESHOLDS["unnecessary_prepare_or_status_rate"]
        and metrics["legacy_tool_hallucination_rate"] <= THRESHOLDS["legacy_tool_hallucination_rate"]
        and metrics["next_action_copy_accuracy"] >= THRESHOLDS["next_action_copy_accuracy"]
        and metrics["original_question_retry_rate"] >= THRESHOLDS["original_question_retry_rate"]
    )
    return {
        "adapter": {"name": adapter.name, "model_version": adapter.model_version},
        "tool_schema_version": _schema_version(tool_schemas),
        "scenario_count": len(SCENARIOS),
        "repeats": REPEATS,
        "thresholds": THRESHOLDS,
        "metrics": metrics,
        "passed": passed,
        "results": results,
    }


def _openai_completion(*, api_base: str, api_key: str, model: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create an opt-in OpenAI-compatible tool-choice completion function."""
    import httpx

    def complete(payload: dict[str, Any]) -> dict[str, Any]:
        scenario = payload["scenario"]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"],
                },
            }
            for tool in payload["tools"]
        ]
        response = httpx.post(
            api_base.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": payload["guidance"]},
                    *(scenario.get("messages") or [
                        {"role": "user", "content": scenario["prompt"]}
                    ]),
                ],
                "tools": tools,
                "tool_choice": "auto",
            },
            timeout=60,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return {"tool": None}
        call = calls[0]["function"]
        arguments = json.loads(call.get("arguments") or "{}")
        return {
            "tool": call["name"],
            "arguments": arguments,
        }

    return complete


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the opt-in live agent tool-choice gate.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-base", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--guidance", type=Path, help="Evaluate an exact installed guidance file instead of the canonical render.")
    args = parser.parse_args(argv)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        parser.error("OPENAI_API_KEY is required for this opt-in live evaluation")
    guidance = args.guidance.read_text(encoding="utf-8") if args.guidance else installed_guidance()
    schemas = public_tool_schemas()
    adapter = OpenAICompatibleLowCostAdapter(
        model_version=args.model,
        completion=_openai_completion(api_base=args.api_base, api_key=api_key, model=args.model),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = evaluate_tool_choice(adapter, guidance=guidance, tool_schemas=schemas)
    except Exception:
        report = {
            "adapter": {"name": adapter.name, "model_version": adapter.model_version},
            "passed": False,
            "reason": "live evaluation failed",
            "status": "failed",
            "tool_schema_version": _schema_version(schemas),
        }
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
