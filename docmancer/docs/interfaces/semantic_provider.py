"""Explicit host-only Responses transport with complete, non-estimated accounting.

Not imported by MCP request handling. A trusted host must provide credentials,
model identity and finite budgets. No implicit model selection, retries, network
fallback, prompt truncation, or credential forwarding to the MCP subprocess.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import time
from typing import Any


class SemanticProviderError(RuntimeError):
    """Sanitized operational failure; never an insufficient-evidence verdict."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def checked_usage(value: Any) -> dict:
    if not isinstance(value, dict):
        raise SemanticProviderError("provider_usage_missing")
    result = deepcopy(value)
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        if type(result.get(name)) is not int or result[name] < 0:
            raise SemanticProviderError("provider_usage_invalid")
    if result["total_tokens"] != result["input_tokens"] + result["output_tokens"]:
        raise SemanticProviderError("provider_usage_inconsistent")
    for group, name, limit in (("input_tokens_details", "cached_tokens", "input_tokens"),
                               ("output_tokens_details", "reasoning_tokens", "output_tokens")):
        details = result.get(group)
        if details is not None and not isinstance(details, dict):
            raise SemanticProviderError("provider_usage_details_invalid")
        count = (details or {}).get(name)
        if count is not None and (type(count) is not int or not 0 <= count <= result[limit]):
            raise SemanticProviderError("provider_usage_details_invalid")
    return result


class ResponsesSemanticProvider:
    """A bounded provider adapter shared by checker, answerer and evaluator.

    records is a PRIVATE audit, not model context. Every attempted request gets
    a receipt, including failures and missing usage. Subtotals are never labeled
    complete totals when an attempt has unknown billing. Cache/reasoning counts
    are details of input/output tokens, never added to total_tokens twice.
    """
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, *, api_key: str, model: str, expected_model: str | None = None,
                 reasoning_effort: str = "medium", max_calls: int = 120,
                 max_total_tokens: int = 300_000, timeout_seconds: float = 120):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("explicit_api_key_required")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("explicit_strong_model_required")
        if expected_model is not None and (not isinstance(expected_model, str) or not expected_model.strip()):
            raise ValueError("invalid_expected_model")
        if reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("invalid_reasoning_effort")
        if any(type(v) is not int or v <= 0 for v in (max_calls, max_total_tokens)):
            raise ValueError("positive_provider_budgets_required")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300):
            raise ValueError("invalid_provider_timeout")
        self._api_key = api_key
        self.model, self.resolved_model = model, expected_model
        self.effort, self.max_calls, self.max_total_tokens = reasoning_effort, max_calls, max_total_tokens
        self.timeout = timeout_seconds
        self._records: list[dict] = []
        self._in_flight = False

    @property
    def records(self) -> list[dict]:
        return deepcopy(self._records)

    def usage_summary(self) -> dict:
        rows = self._records
        known = [row["usage"] for row in rows if row.get("usage") is not None]
        complete = len(known) == len(rows)
        subtotal = {k: sum(row[k] for row in known)
                    for k in ("input_tokens", "output_tokens", "total_tokens")}
        details = {}
        for group, key in (("input_tokens_details", "cached_tokens"),
                           ("output_tokens_details", "reasoning_tokens")):
            values = [(row.get(group) or {}).get(key) for row in known]
            details[key] = sum(values) if complete and all(v is not None for v in values) else None
        return {"attempted_calls": len(rows), "accounted_calls": len(known),
                "accounting_complete": complete, "provider_totals": subtotal if complete else None,
                "known_subtotal": subtotal, **details, "requested_model": self.model,
                "resolved_model": self.resolved_model, "estimated_usage": False}

    async def complete(self, *, purpose: str, instruction: str, payload: dict,
                       schema: dict, max_output_tokens: int = 4096) -> dict:
        import httpx
        from jsonschema import Draft202012Validator

        if self._in_flight:
            raise SemanticProviderError("concurrent_provider_call_not_supported")
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 16384:
            raise ValueError("invalid_output_budget")
        summary = self.usage_summary()
        if not summary["accounting_complete"]:
            raise SemanticProviderError("unaccounted_previous_provider_attempt")
        if len(self._records) >= self.max_calls or summary["known_subtotal"]["total_tokens"] >= self.max_total_tokens:
            raise SemanticProviderError("provider_budget_exhausted")
        # A conservative preflight bound on this text-only request, not a usage
        # estimate. Actual consumption is always read from the provider response.
        request = {"model": self.model, "store": False,
                   "input": [{"role": "system", "content": instruction},
                             {"role": "user", "content": _json(payload)}],
                   "reasoning": {"effort": self.effort}, "max_output_tokens": max_output_tokens,
                   "text": {"format": {"type": "json_schema", "name": "docatlas_semantic_v1",
                                        "strict": True, "schema": schema}}}
        Draft202012Validator.check_schema(schema)
        wire = _json(request).encode()
        if len(wire) > 512_000:
            raise SemanticProviderError("provider_request_limit_no_truncation")
        if summary["known_subtotal"]["total_tokens"] + len(wire) + max_output_tokens > self.max_total_tokens:
            raise SemanticProviderError("provider_remaining_budget_too_small")
        receipt = {"purpose": purpose, "request_sha256": hashlib.sha256(wire).hexdigest(),
                   "requested_model": self.model, "request": request, "usage": None,
                   "request_id": None, "response_id": None, "status": "attempted"}
        self._records.append(receipt)
        self._in_flight = True
        begin = time.monotonic()
        try:
            # Do not inherit proxy settings or follow redirects with credentials.
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                response = await client.post(self.endpoint, content=wire, headers={
                    "Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"})
            receipt["http_status"] = response.status_code
            receipt["request_id"] = response.headers.get("x-request-id")
            if response.status_code != 200:
                raise SemanticProviderError("provider_http_" + str(response.status_code))
            body = response.json()
            if not isinstance(body, dict):
                raise SemanticProviderError("provider_response_invalid")
            receipt["response_id"] = body.get("id")
            receipt["usage"] = checked_usage(body.get("usage"))
            receipt["resolved_model"] = body.get("model")
            receipt["provider_status"] = body.get("status")
            # Retain provider-visible message content and IDs, not credentials or
            # private reasoning fields. Usage includes billed reasoning tokens.
            receipt["output_messages"] = [item for item in body.get("output", [])
                                          if isinstance(item, dict) and item.get("type") == "message"]
            resolved = body.get("model")
            if not isinstance(resolved, str) or not resolved:
                raise SemanticProviderError("provider_model_identity_missing")
            if self.resolved_model is not None and resolved != self.resolved_model:
                raise SemanticProviderError("provider_model_identity_changed")
            self.resolved_model = resolved
            if not receipt["request_id"] or not receipt["response_id"]:
                raise SemanticProviderError("provider_request_identity_missing")
            if body.get("status") != "completed":
                raise SemanticProviderError("provider_response_not_complete")
            blocks = [block for item in receipt["output_messages"] for block in item.get("content", [])]
            if any(block.get("type") == "refusal" for block in blocks):
                raise SemanticProviderError("provider_refusal")
            text = "".join(block.get("text", "") for block in blocks if block.get("type") == "output_text")
            value = json.loads(text, object_pairs_hook=_unique_object)
            Draft202012Validator(schema).validate(value)
            receipt["status"] = "completed"
            return {"value": deepcopy(value), "model": resolved,
                    "usage": deepcopy(receipt["usage"]), "request_id": receipt["request_id"],
                    "response_id": receipt["response_id"]}
        except Exception as exc:
            reason = str(exc) if isinstance(exc, SemanticProviderError) else type(exc).__name__
            receipt.update(status="error", error_code=reason)
            raise SemanticProviderError(reason) from None
        finally:
            receipt["seconds"] = time.monotonic() - begin
            self._in_flight = False
