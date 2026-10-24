"""Bound, provider-neutral MCP client state for economical documentation turns.

The host, not retrieved text, owns bindings, mode, limits and invalidation.
This is a real MCP client adapter, not an LLM, translator or semantic judge.
model_input() is the ONLY projection intended for the answering model. Audit,
opaque continuation URIs and MCP _meta never enter that projection.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from docmancer.docs.application.model_context_view import (
    canonical, encode_model_result, restore_model_result,
)
from docmancer.docs.application.section_compression import expand_sections, OUTPUT_LIMIT
from docmancer.docs.application.projection_tokenizer import projection_token_count
from .host_context import extract_tool_payload


class ModelSessionError(ValueError):
    """An operational boundary, never a successful semantic refusal."""


def _wire(result: Any) -> dict:
    value = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result
    if not isinstance(value, dict):
        raise ModelSessionError("invalid_mcp_result")
    return deepcopy(value)


def _status(result: Any) -> dict:
    value = _wire(result)
    if value.get("isError"):
        raise ModelSessionError("status_failed")
    structured = value.get("structuredContent")
    bodies = []
    for block in value.get("content") or []:
        if block.get("type") != "text":
            continue
        try:
            item = json.loads(block.get("text", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(item, dict):
            bodies.append(item)
    if len(bodies) > 1 or (structured is not None and not isinstance(structured, dict)):
        raise ModelSessionError("ambiguous_status")
    if structured is not None:
        if bodies and canonical(bodies[0]) != canonical(structured):
            raise ModelSessionError("conflicting_status_channels")
        return structured
    if len(bodies) != 1:
        raise ModelSessionError("missing_status")
    return bodies[0]


class ModelContextSession:
    """One concrete question, immutable source bindings, bounded private audit.

    For language mode the host must call language() before retrieve(). Unknown
    metadata never guesses English. The strong model supplies search_question.
    A different search after the first needs a concrete caller-assessed gap.
    Repeated identical arguments are refused before another product request.

    Snapshots are rechecked through language(refresh=True) on explicit refresh;
    hosts MUST invalidate() on any project/catalog/dependency/access change.
    No source state, language or citations are cached across independent turns.
    """

    def __init__(self, client: Any, *, question: str, bindings: dict,
                 language_mode: bool = False, canonical_id: str | None = None,
                 max_input_tokens: int = OUTPUT_LIMIT, max_searches: int = 3,
                 max_events: int = 12):
        allowed = {"project_path", "library", "version", "module_path", "scope"}
        if not isinstance(question, str) or not question.strip():
            raise ModelSessionError("question_required")
        if set(bindings) - allowed or not (bindings.get("project_path") or bindings.get("library")):
            raise ModelSessionError("exact_source_bindings_required")
        if bindings.get("module_path") and bindings.get("scope") not in (None, "module"):
            raise ModelSessionError("conflicting_module_scope")
        if type(language_mode) is not bool:
            raise ModelSessionError("invalid_language_mode")
        if language_mode and bindings.get("scope") == "all":
            raise ModelSessionError("language_preflight_requires_exact_scope")
        for value in (max_input_tokens, max_searches, max_events):
            if type(value) is not int or value < 1:
                raise ModelSessionError("invalid_host_budget")
        self.client = client
        self._question = question
        self._bindings = deepcopy(bindings)
        self._canonical_id = canonical_id
        self._language_mode = language_mode
        self._limit, self._max_searches, self._max_events = max_input_tokens, max_searches, max_events
        self._audit: list[dict] = []
        self._language: dict | None = None
        self._snapshot: str | None = None
        self._events: list[dict] = []
        self._sources: dict[str, dict] = {}
        self._originals: dict[str, dict] = {}
        self._identities: dict[str, str] = {}
        self._seen: set[str] = set()
        self._searches = 0
        self._recommended: dict | None = None
        self._tools: list[dict] = []

    @property
    def audit(self) -> list[dict]:
        """Private full transport records; never feed these to the model."""
        return deepcopy(self._audit)

    def invalidate(self) -> None:
        """Host explicit source/version/access change: drop active, not audit."""
        self._language = None
        self._snapshot = None
        self._events.clear()
        self._sources.clear()
        self._originals.clear()
        self._identities.clear()
        self._seen.clear()
        self._recommended = None
        # Search/event ceilings do not reset: invalidation is not a budget bypass.

    def _room(self) -> None:
        if len(self._audit) >= self._max_events:
            raise ModelSessionError("session_event_limit")

    async def tools(self, *, lifecycle_requested: bool = False) -> list[dict]:
        """Only expose relevant definitions; the server keeps all three tools."""
        if not self._tools:
            response = await self.client.list_tools()
            self._tools = [tool.model_dump(exclude_none=True) for tool in response.tools]
        names = {"get_docs_context"}
        if self._language_mode and self._language is None:
            names = {"docs_status"}
        if lifecycle_requested or (self._recommended or {}).get("tool") == "prepare_docs":
            names.add("prepare_docs")
        # This adapter never executes lifecycle changes or supplies confirmations.
        return deepcopy([tool for tool in self._tools if tool["name"] in names])

    async def language(self, *, refresh: bool = False) -> dict:
        if self._language is not None and not refresh:
            return deepcopy(self._language)
        self._room()
        if self._bindings.get("library"):
            if not self._canonical_id:
                raise ModelSessionError("bound_library_canonical_id_required")
            request = {"action": "library", "canonical_id": self._canonical_id}
        else:
            request = {"action": "project", "project_path": self._bindings["project_path"]}
            if self._bindings.get("module_path"):
                request["module"] = self._bindings["module_path"]
        request["include_language"] = True
        result = await self.client.call_tool("docs_status", request)
        self._audit.append({"tool": "docs_status", "arguments": deepcopy(request), "result": _wire(result)})
        profile = _status(result).get("documentation_language")
        if not isinstance(profile, dict):
            raise ModelSessionError("language_metadata_unavailable")
        snapshot = profile.get("snapshot_sha256")
        if snapshot != self._snapshot:
            self.invalidate()
        self._snapshot = snapshot if isinstance(snapshot, str) and snapshot else None
        self._language = deepcopy(profile)
        return deepcopy(profile)

    async def retrieve(self, *, search_question: str | None = None,
                       lookup_queries: list[str] | None = None,
                       missing_fact: str | None = None) -> dict:
        if self._language_mode and self._language is None:
            raise ModelSessionError("language_preflight_required")
        if self._searches >= self._max_searches:
            raise ModelSessionError("session_search_limit")
        if self._searches and (not isinstance(missing_fact, str) or not missing_fact.strip()):
            raise ModelSessionError("concrete_gap_required")
        request = {**self._bindings, "question": self._question}
        if search_question is not None:
            if not isinstance(search_question, str) or not search_question.strip():
                raise ModelSessionError("invalid_search_question")
            if self._language_mode and (self._language or {}).get("status") != "declared":
                raise ModelSessionError("translation_language_unresolved")
            request["search_question"] = search_question
        if lookup_queries is not None:
            request["lookup_queries"] = deepcopy(lookup_queries)
        fingerprint = canonical(request)
        if fingerprint in self._seen:
            raise ModelSessionError("duplicate_retrieval")
        self._room()
        self._seen.add(fingerprint)
        self._searches += 1
        result = await self.client.call_tool("get_docs_context", request)
        raw = _wire(result)
        self._audit.append({"tool": "get_docs_context", "arguments": deepcopy(request), "result": raw})
        if raw.get("isError"):
            self.invalidate()
            self._events.append({"error": _status_error(raw)})
            raise ModelSessionError("retrieval_failed")
        try:
            packet = extract_tool_payload(result)
            payload = expand_sections(packet)
            encoded = encode_model_result(packet)
        except (ValueError, KeyError, TypeError) as exc:
            self.invalidate()
            raise ModelSessionError("invalid_evidence_delivery") from exc
        if encoded is None:
            self._events.clear()
            self._sources.clear()
            self._originals.clear()
            self._identities.clear()
            # Preserve actual denial/recovery, never convert it into semantic absence.
            self._recommended = deepcopy(payload.get("recommended_next_action"))
            self._events.append({"result": deepcopy(payload)})
            return self.model_input()
        view, meta = encoded
        restore_model_result(view, meta)
        # Dedup only exact content+provenance in the SAME explicitly bound snapshot.
        # Without a snapshot, keep response-local identities rather than guess.
        binding = {"source": self._bindings, "snapshot": self._snapshot}
        new_sources = deepcopy(self._sources)
        new_originals = deepcopy(self._originals)
        new_identities = dict(self._identities)
        refs = []
        for display, source in zip(view["sources"], payload["sources"], strict=True):
            identity_row = source  # include issued snapshot-bound URI and all provenance
            identity = canonical({"binding": binding, "row": identity_row,
                "unverified_snapshot_response": None if self._snapshot and source.get("source_uri")
                    else [len(self._audit), display["ref"]]})
            ref = "s" + hashlib.sha256(identity.encode()).hexdigest()[:20]
            if ref in new_identities and new_identities[ref] != identity:
                raise ModelSessionError("citation_collision")
            new_identities[ref] = identity
            item = {**deepcopy(view.get("source_context") or {}), **deepcopy(display), "ref": ref}
            new_sources[ref] = item
            new_originals[ref] = deepcopy(source)  # newest issued continuation, never invented
            refs.append(ref)
        event = {k: deepcopy(v) for k, v in view.items() if k not in {"sources", "source_context"}}
        event["source_refs"] = list(dict.fromkeys(refs))
        if missing_fact is not None:
            event["caller_assessed_gap"] = missing_fact
        candidate = self._input(new_sources, [*self._events, event])
        self._check_budget(candidate)
        self._sources, self._originals, self._identities = new_sources, new_originals, new_identities
        self._events.append(event)
        self._recommended = deepcopy(payload.get("recommended_next_action"))
        return candidate

    def _input(self, sources: dict, events: list) -> dict:
        return {"question": self._question, "language": deepcopy(self._language),
                "results": deepcopy(events), "sources": deepcopy(list(sources.values()))}

    def _check_budget(self, value: dict) -> None:
        if projection_token_count(canonical(value).encode()) > self._limit:
            raise ModelSessionError("model_input_budget_exceeded")

    def model_input(self) -> dict:
        """Fresh deduplicated input, NOT an append-only transcript or full prompt."""
        value = self._input(self._sources, self._events)
        self._check_budget(value)
        return value

    def resolve(self, reference: str) -> dict:
        if reference not in self._originals:
            raise ModelSessionError("unknown_or_invalidated_reference")
        return deepcopy(self._originals[reference])


def _status_error(value: dict) -> dict:
    """Keep an operational error's public explanation, not private metadata."""
    blocks = value.get("content") or []
    return {"isError": True, "content": deepcopy(blocks)}
