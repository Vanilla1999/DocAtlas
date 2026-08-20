#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from eval.agent_developer_v1.model_benchmark import action_schema, run_benchmark


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_API_BASE = "https://api.openai.com/v1"
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _output_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
    return "".join(chunks)


def _strict_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"OpenAI Responses usage omitted valid {name}")
    return value


class OpenAIAPIPlanner:
    provider_id = "openai-api"

    def __init__(
        self,
        token: str,
        *,
        model: str = DEFAULT_MODEL,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        if not token.strip():
            raise ValueError("OpenAI API token is required")
        self.model = model
        self._token = token
        self._api_base = api_base.rstrip("/")

    def choose(self, messages: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
        request_payload = {
            "model": self.model,
            "input": messages,
            "max_output_tokens": 768,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_developer_evidence_action_v1",
                    "strict": True,
                    "schema": action_schema(),
                }
            },
        }
        serialized = json.dumps(
            request_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response: httpx.Response | None = None
        for attempt in range(4):
            response = httpx.post(
                self._api_base + "/responses",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                content=serialized,
                timeout=90,
            )
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                break
            if attempt == 3:
                break
            time.sleep(2.0 * (2**attempt))
        assert response is not None
        response.raise_for_status()
        request_id = str(response.headers.get("x-request-id") or "").strip()
        if not request_id:
            raise RuntimeError("OpenAI Responses result omitted x-request-id")

        body = response.json()
        text = _output_text(body)
        if not text:
            raise RuntimeError("OpenAI Responses result omitted structured output text")
        action = json.loads(text)
        if not isinstance(action, dict):
            raise RuntimeError("OpenAI Responses structured output is not an object")

        raw_usage = body.get("usage")
        if not isinstance(raw_usage, dict):
            raise RuntimeError("OpenAI Responses result omitted usage")
        input_tokens = _strict_nonnegative_int(raw_usage.get("input_tokens"), "input_tokens")
        output_tokens = _strict_nonnegative_int(raw_usage.get("output_tokens"), "output_tokens")
        total_tokens = _strict_nonnegative_int(raw_usage.get("total_tokens"), "total_tokens")
        if total_tokens != input_tokens + output_tokens:
            raise RuntimeError("OpenAI Responses usage totals are inconsistent")
        details = raw_usage.get("output_tokens_details")
        reasoning_tokens = None
        if isinstance(details, dict) and details.get("reasoning_tokens") is not None:
            reasoning_tokens = _strict_nonnegative_int(
                details.get("reasoning_tokens"), "reasoning_tokens"
            )

        response_id = str(body.get("id") or "").strip()
        request_ids = {"x-request-id": request_id}
        if response_id:
            request_ids["response-id"] = response_id
        usage = {
            "request_id": request_id,
            "request_ids": request_ids,
            "model": str(body.get("model") or self.model),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "request_payload_sha256": hashlib.sha256(serialized).hexdigest(),
            "estimated_input_tokens": max(1, len(serialized) // 4),
        }
        return action, usage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the model-backed Agent Developer benchmark through the OpenAI Responses API"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "eval" / "agent_developer_v1" / "results" / "model-benchmark.json",
    )
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    args = parser.parse_args(argv)
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    token = os.environ.get("OPENAI_API_KEY") or ""
    if not token.strip():
        print("Agent Developer OpenAI benchmark: missing OPENAI_API_KEY")
        return 2

    planner = OpenAIAPIPlanner(
        token,
        model=args.model,
        api_base=args.api_base,
    )
    report = run_benchmark(planner, task_ids=set(args.tasks) if args.tasks else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Agent Developer OpenAI benchmark: {report['passed_tasks']}/{report['task_count']} "
        f"pass; scope={report['scope_accuracy']:.3f}; recovery={report['recovery_accuracy']:.3f}; "
        f"false-supported={report['false_supported']}; contamination={report['forbidden_source_contamination']}"
    )
    if report["infrastructure_errors"]:
        for error in report["infrastructure_errors"]:
            print(f"- infrastructure: {error}")
        return 2
    return 0 if float(report["pass_rate"]) >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
