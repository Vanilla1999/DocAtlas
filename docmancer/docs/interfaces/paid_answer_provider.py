"""Explicit paid Responses API adapter; no credentials/model auto-discovery.

A caller authorizes this provider and supplies a per-instance call ceiling.
No tools, retries, automatic truncation, content logging or local-token billing.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import http.client
import json
import time

from docmancer.docs.application.semantic_sufficiency import canonical, fingerprint


class PaidAnswerProvider:
    def __init__(self, *, api_key: str, model: str, max_calls: int = 12,
                 timeout_seconds: int = 180):
        if not isinstance(api_key, str) or not api_key.strip() or not isinstance(model, str) or not model.strip():
            raise ValueError("explicit_paid_credentials_and_model_required")
        if type(max_calls) is not int or not 1 <= max_calls <= 100:
            raise ValueError("invalid_paid_call_budget")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 300:
            raise ValueError("invalid_paid_timeout")
        self._key, self.model, self._maximum, self._timeout = api_key, model, max_calls, timeout_seconds
        self.records = []
        self._lock = asyncio.Lock()

    async def complete(self, *, purpose, instruction, payload, schema, max_output_tokens):
        async with self._lock:
            if len(self.records) >= self._maximum:
                raise ValueError("paid_call_limit")
            if type(max_output_tokens) is not int or not 16 <= max_output_tokens <= 4096:
                raise ValueError("invalid_paid_output_budget")
            request = {"model": self.model, "instructions": instruction,
                       "input": canonical(payload), "store": False,
                       "truncation": "disabled", "max_output_tokens": max_output_tokens,
                       "text": {"format": {"type": "json_schema", "name": "grounded_answer",
                                              "strict": True, "schema": schema}}}
            wire = canonical(request).encode()
            if len(wire) > 524288:
                raise ValueError("paid_request_limit_no_truncation")
            record = {"purpose": purpose, "requested_model": self.model,
                      "request_sha256": fingerprint(wire.decode()), "status": "attempted",
                      "usage": None, "usage_known": False}
            self.records.append(record)
            start = time.monotonic()
            try:
                body = await asyncio.to_thread(self._post, wire)
                if isinstance(body.get("usage"), dict):
                    record["usage"] = deepcopy(body["usage"])
                usage = body.get("usage") or {}
                keys = ("input_tokens", "output_tokens", "total_tokens")
                if (any(type(usage.get(k)) is not int or usage[k] < 0 for k in keys)
                        or usage["input_tokens"] + usage["output_tokens"] != usage["total_tokens"]):
                    raise ValueError("paid_usage_unavailable")
                record.update(usage_known=True, response_id=body.get("id"), response_model=body.get("model"))
                if body.get("status") != "completed":
                    raise ValueError("paid_generation_incomplete")
                text = "".join(part["text"] for item in body.get("output", [])
                               if item.get("type") == "message"
                               for part in item.get("content", []) if part.get("type") == "output_text")
                value = json.loads(text)
                from jsonschema import Draft202012Validator
                Draft202012Validator(schema).validate(value)
                record["status"] = "completed"
                return {"value": value, "model": body.get("model"), "request_id": record["request_sha256"],
                        "response_id": body.get("id"), "usage": deepcopy(usage)}
            except Exception as exc:
                record.update(status="failed", error_type=type(exc).__name__)
                raise
            finally:
                record["seconds"] = time.monotonic() - start

    def _post(self, wire):
        conn = http.client.HTTPSConnection("api.openai.com", timeout=self._timeout)
        try:
            conn.request("POST", "/v1/responses", body=wire,
                         headers={"Authorization": "Bearer " + self._key,
                                  "Content-Type": "application/json"})
            response = conn.getresponse()
            data = response.read(1048577)
            if response.status != 200 or len(data) > 1048576:
                raise ValueError("paid_provider_http_failure")
            return json.loads(data)
        finally:
            conn.close()
