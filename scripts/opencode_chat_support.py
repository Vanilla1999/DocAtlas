#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import jsonschema


REPORT_MODEL = "gpt-5.6-luna"
DEFAULT_OPENCODE_MODEL = "openai/gpt-5.6-luna"
OPENCODE_VARIANT = "medium"


class OpenCodeChatError(RuntimeError):
    """Infrastructure/provider failure while invoking OpenCode."""


class OpenCodeModelOutputError(OpenCodeChatError):
    """The model answered, but never produced one schema-valid JSON object."""

    def __init__(self, message: str, *, usage: dict[str, Any]) -> None:
        super().__init__(message)
        self.usage = usage


def canonical_model_name(model_id: str) -> str:
    return str(model_id).strip().rsplit("/", 1)[-1]


def _json_object_candidates(text: str) -> list[dict[str, Any]]:
    """Extract distinct JSON objects without trusting surrounding prose/fences."""
    raw = str(text or "")
    decoder = json.JSONDecoder()
    found: dict[str, dict[str, Any]] = {}

    def add(value: Any) -> None:
        if not isinstance(value, dict):
            return
        key = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        found[key] = value

    stripped = raw.strip()
    if stripped:
        try:
            add(json.loads(stripped))
        except json.JSONDecodeError:
            pass

    # OpenCode/model output may contain prose, ```json fences, or several text
    # chunks concatenated together. raw_decode from every object boundary keeps
    # extraction tolerant while schema validation below remains fail-closed.
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        add(value)

    return list(found.values())


def _schema_json_object(
    texts: list[str],
    schema: dict[str, Any],
) -> dict[str, Any]:
    valid: dict[str, dict[str, Any]] = {}
    for text in texts:
        for candidate in _json_object_candidates(text):
            try:
                jsonschema.validate(candidate, schema)
            except jsonschema.ValidationError:
                continue
            key = json.dumps(
                candidate,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            valid[key] = candidate

    if len(valid) == 1:
        return next(iter(valid.values()))
    if not valid:
        raise OpenCodeChatError(
            "OpenCode response did not contain one schema-valid JSON object"
        )
    raise OpenCodeChatError(
        "OpenCode response contained multiple distinct schema-valid JSON objects"
    )


def build_opencode_prompt(
    *,
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    purpose: str,
) -> str:
    return (
        "You are the model-under-test in a DocAtlas benchmark.\n"
        "Do not use tools, files, shell, web, subagents, skills, MCP, or external context. "
        "Everything you are allowed to see is embedded below.\n"
        "Answer the supplied conversation as the assistant. Return exactly ONE JSON object "
        "matching the JSON Schema. Do not use markdown fences or explanatory prose.\n\n"
        f"Benchmark purpose: {purpose}\n\n"
        "Conversation JSON:\n"
        + json.dumps(messages, ensure_ascii=False, sort_keys=True)
        + "\n\nOutput JSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False, sort_keys=True)
    )


def _event_text_and_usage(stdout: str) -> tuple[str, str | None, dict[str, int]]:
    chunks: list[str] = []
    session_id: str | None = None
    usage = {"input": 0, "output": 0, "reasoning": 0}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("sessionID"), str) and event["sessionID"]:
            session_id = event["sessionID"]
        part = event.get("part")
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            chunks.append(part["text"])
        if part.get("type") == "step-finish" and isinstance(part.get("tokens"), dict):
            tokens = part["tokens"]
            for key in usage:
                value = tokens.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    usage[key] = value
    return "".join(chunks).strip(), session_id, usage


def _walk_text(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            found.append(value["text"])
        for child in value.values():
            found.extend(_walk_text(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_text(child))
    return found


def _export_schema_text(
    executable: str,
    session_id: str,
    env: dict[str, str],
    schema: dict[str, Any],
) -> str:
    completed = subprocess.run(
        [executable, "export", session_id],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return ""
    for candidate in reversed(_walk_text(payload)):
        try:
            _schema_json_object([candidate], schema)
        except OpenCodeChatError:
            continue
        return candidate
    return ""


def _safe_failure_detail(stderr: str) -> str:
    text = " ".join(str(stderr or "").split())
    return text[:400] if text else "no stderr"


class OpenCodeJSONClient:
    def __init__(
        self,
        *,
        model_id: str = DEFAULT_OPENCODE_MODEL,
        variant: str = OPENCODE_VARIANT,
        executable: str = "opencode",
        timeout_seconds: int = 180,
        format_attempts: int = 2,
    ) -> None:
        if canonical_model_name(model_id) != REPORT_MODEL:
            raise ValueError(f"OpenCode live closure is pinned to {REPORT_MODEL}")
        if variant != OPENCODE_VARIANT:
            raise ValueError(f"OpenCode live closure is pinned to variant {OPENCODE_VARIANT}")
        if format_attempts < 1:
            raise ValueError("format_attempts must be positive")
        resolved = shutil.which(executable)
        if not resolved:
            raise OpenCodeChatError(f"OpenCode executable not found: {executable}")
        self.model_id = model_id
        self.model = REPORT_MODEL
        self.variant = variant
        self.executable = resolved
        self.timeout_seconds = timeout_seconds
        self.format_attempts = format_attempts

    def complete_json(
        self,
        *,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        purpose: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        base_prompt = build_opencode_prompt(
            messages=messages,
            schema=schema,
            purpose=purpose,
        )
        env = os.environ.copy()
        last_parse_error: OpenCodeChatError | None = None
        session_ids: list[str] = []
        prompt_digests: list[str] = []
        total_tokens = {"input": 0, "output": 0, "reasoning": 0}
        estimated_input_tokens = 0

        for attempt in range(self.format_attempts):
            prompt = base_prompt
            if attempt:
                prompt += (
                    "\n\nFORMAT RETRY: Return one complete JSON object only. "
                    "Do not truncate it, wrap it in markdown, or emit a second object."
                )
            prompt_digests.append(hashlib.sha256(prompt.encode("utf-8")).hexdigest())
            estimated_input_tokens += max(1, len(prompt) // 4)

            with TemporaryDirectory(prefix="docatlas-opencode-eval-") as raw_tmp:
                workspace = Path(raw_tmp)
                (workspace / "opencode.json").write_text(
                    json.dumps(
                        {
                            "$schema": "https://opencode.ai/config.json",
                            "permission": "deny",
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [
                        self.executable,
                        "run",
                        "--format",
                        "json",
                        "--model",
                        self.model_id,
                        "--variant",
                        self.variant,
                        "--dir",
                        str(workspace),
                        prompt,
                    ],
                    cwd=workspace,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout_seconds,
                    check=False,
                )

            text, session_id, tokens = _event_text_and_usage(completed.stdout)
            if session_id:
                session_ids.append(session_id)
            for key in total_tokens:
                total_tokens[key] += int(tokens.get(key) or 0)

            if completed.returncode != 0:
                raise OpenCodeChatError(
                    f"opencode run failed exit={completed.returncode}: "
                    f"{_safe_failure_detail(completed.stderr)}"
                )

            candidate_texts = [text] if text else []
            try:
                result = _schema_json_object(candidate_texts, schema)
            except OpenCodeChatError as exc:
                last_parse_error = exc
                if session_id:
                    exported = _export_schema_text(
                        self.executable,
                        session_id,
                        env,
                        schema,
                    )
                    if exported:
                        try:
                            result = _schema_json_object(
                                [*candidate_texts, exported],
                                schema,
                            )
                        except OpenCodeChatError as export_exc:
                            last_parse_error = export_exc
                        else:
                            return result, self._usage(
                                session_ids=session_ids,
                                prompt_digests=prompt_digests,
                                tokens=total_tokens,
                                estimated_input_tokens=estimated_input_tokens,
                            )
                if attempt + 1 < self.format_attempts:
                    continue
                raise OpenCodeModelOutputError(
                    str(last_parse_error),
                    usage=self._usage(
                        session_ids=session_ids,
                        prompt_digests=prompt_digests,
                        tokens=total_tokens,
                        estimated_input_tokens=estimated_input_tokens,
                    ),
                ) from last_parse_error
            else:
                return result, self._usage(
                    session_ids=session_ids,
                    prompt_digests=prompt_digests,
                    tokens=total_tokens,
                    estimated_input_tokens=estimated_input_tokens,
                )

        raise OpenCodeModelOutputError(
            str(last_parse_error or "OpenCode response did not contain one schema-valid JSON object"),
            usage=self._usage(
                session_ids=session_ids,
                prompt_digests=prompt_digests,
                tokens=total_tokens,
                estimated_input_tokens=estimated_input_tokens,
            ),
        )

    def _usage(
        self,
        *,
        session_ids: list[str],
        prompt_digests: list[str],
        tokens: dict[str, int],
        estimated_input_tokens: int,
    ) -> dict[str, Any]:
        if len(prompt_digests) == 1:
            digest = prompt_digests[0]
        else:
            digest = hashlib.sha256("|".join(prompt_digests).encode("utf-8")).hexdigest()
        request_ids = {
            f"opencode-session-{index}": session_id
            for index, session_id in enumerate(session_ids, start=1)
        }
        if request_ids:
            request_id = session_ids[-1]
        else:
            request_id = f"opencode-{digest[:24]}"
            request_ids = {"opencode-attempt": request_id}
        return {
            "request_id": request_id,
            "request_ids": request_ids,
            "model": self.model,
            "reasoning_effort": self.variant,
            "input_tokens": int(tokens.get("input") or 0),
            "output_tokens": int(tokens.get("output") or 0),
            "reasoning_tokens": int(tokens.get("reasoning") or 0),
            "request_payload_sha256": digest,
            "estimated_input_tokens": max(1, int(estimated_input_tokens)),
        }
