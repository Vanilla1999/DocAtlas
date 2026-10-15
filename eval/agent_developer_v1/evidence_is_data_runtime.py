"""P1.6 public-delivery fixture; retrieval is injected, MCP serialization is real.

Raw frozen evidence and wire text exist only in this process. The report module
persists frozen range references and digests. This is not indexed retrieval,
a stdio/client session, or an autonomous model/agent execution.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
from importlib.metadata import version
import json
from unittest.mock import patch


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _candidate(case: dict) -> dict:
    # Original P1.6 candidate constructor: do not add facts, roles or permissions.
    text = str(case["candidate_text"])
    source = str(case["candidate_source"])
    return {
        "stable_chunk_id": f"p1.6:{case['id']}",
        "parent_logical_id": f"document:{source}",
        "source": source,
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "authority": str(case["candidate_authority"]),
        "source_class": str(case["candidate_source_class"]),
        "docs_exactness": "exact",
        "version": "project",
        "retrieval_rank": 1,
        "score": 1.0,
    }


def serialize_delivery(payload: dict) -> dict:
    """Use the installed real MCP model and the server's exact two formatters."""
    import mcp.types as mcp_types
    from docmancer.mcp._docs_server_part01 import _mcp_tool_result

    deliveries = {}
    for name, fallback in (("structured", False), ("text_fallback", True)):
        result = _mcp_tool_result(mcp_types, deepcopy(payload), text_fallback=fallback)
        wire = result.model_dump_json(by_alias=True, exclude_none=True)
        frame = json.loads(wire)
        text_blocks = [row["text"] for row in frame["content"] if row.get("type") == "text"]
        delivered = json.loads(text_blocks[0]) if fallback else frame.get("structuredContent")
        # Do not retain raw wire/text in the report; these are actual wire receipts.
        envelope = deepcopy(frame)
        envelope.pop("structuredContent", None)
        for row in envelope["content"]:
            if "text" in row:
                text = row.pop("text")
                row["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
                row["text_utf8_bytes"] = len(text.encode("utf-8"))
        deliveries[name] = {
            "payload": delivered, "payload_sha256": sha256_json(delivered),
            "envelope": envelope,
            "wire_sha256": hashlib.sha256(wire.encode("utf-8")).hexdigest(),
            "wire_utf8_bytes": len(wire.encode("utf-8")),
            "model": f"{type(result).__module__}.{type(result).__name__}",
        }
    return {"mcp_version": version("mcp"), "formats": deliveries}


def reserialize_capture(capture: dict, *, revalidate: bool = False) -> dict:
    """Oracle fault injections replay a captured payload through real code."""
    result = deepcopy(capture)
    if revalidate:
        from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
        snapshot = deepcopy(result["validation_calls"][0]["snapshot"])
        errors = validate_model_visible_projection(result["public_payload"], snapshot=snapshot)
        result["validation_calls"] = [{
            "payload": deepcopy(result["public_payload"]), "snapshot": snapshot,
            "errors": list(errors), "max_tokens": None, "canonical_selection_present": False,
        }]
    result["delivery"] = serialize_delivery(result["public_payload"])
    return result


def capture_case(case: dict) -> dict:
    from docmancer.docs.interfaces.mcp import context_tools
    from docmancer.mcp import _docs_server_part01 as server

    class FrozenRetrieval:
        """Only the retrieval boundary is replaced; every access is observable."""
        def __init__(self):
            self.unified_context = self
            self._same_call_diagnostics_observer = None
            self.calls = []
            self.unexpected_access = []

        def get_docs_context(self, question, **kwargs):
            self.calls.append({"method": "get_docs_context", "question": question, "arguments": deepcopy(kwargs)})
            return {
                "status": "success", "answer_available": True,
                "context_pack": [_candidate(case)],
                "public_requirements": deepcopy(case["public_requirements"]),
                "trust_contract": {},
            }

        def __getattr__(self, name):
            self.unexpected_access.append(name)
            raise AttributeError(name)

    service = FrozenRetrieval()
    dispatch_calls, projection_calls, validation_calls = [], [], []
    dispatch = server.call_docs_tool_payload
    project = context_tools.project_docs_answer
    validate = context_tools.validate_model_visible_projection

    @wraps(dispatch)
    def observe_dispatch(name, arguments, owner, **kwargs):
        dispatch_calls.append({"tool": name, "arguments": deepcopy(arguments)})
        return dispatch(name, arguments, owner, **kwargs)

    @wraps(project)
    def observe_projection(**kwargs):
        retrieval = kwargs["retrieval"]
        projection_calls.append({
            "question": kwargs["question"],
            "context_pack": deepcopy(retrieval.get("context_pack")),
            "public_requirements": deepcopy(retrieval.get("public_requirements")),
            "trust_contract": deepcopy(retrieval.get("trust_contract")),
            "document_content_policy": deepcopy(retrieval.get("document_content_policy")),
            "control_fields": {key: deepcopy(retrieval[key]) for key in (
                "next_action", "next_actions", "recommended_next_action", "auto_execute", "requires_confirmation",
                "hard_stop", "authorized_actions", "mutation_actions", "mutation_authorized",
            ) if key in retrieval},
        })
        return project(**kwargs)

    @wraps(validate)
    def observe_validation(payload, **kwargs):
        errors = validate(payload, **kwargs)
        validation_calls.append({
            "payload": deepcopy(payload), "snapshot": deepcopy(kwargs.get("snapshot")),
            "errors": list(errors), "max_tokens": kwargs.get("max_tokens"),
            "canonical_selection_present": kwargs.get("canonical_selection") is not None,
        })
        return errors

    request = {"question": case["question"]}
    with patch.object(server, "call_docs_tool_payload", observe_dispatch), \
            patch.object(context_tools, "project_docs_answer", observe_projection), \
            patch.object(context_tools, "validate_model_visible_projection", observe_validation):
        payload = server.call_docs_tool_payload("get_docs_context", request, service)
    return {
        "request": request, "dispatch_calls": dispatch_calls,
        "facade_calls": deepcopy(service.calls), "unexpected_service_access": list(service.unexpected_access),
        "projection_calls": projection_calls, "validation_calls": validation_calls,
        "public_payload": deepcopy(payload), "delivery": serialize_delivery(payload),
    }
