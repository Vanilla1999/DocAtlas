"""Bounded source continuation; references never grant additional authority."""
from __future__ import annotations

from collections import OrderedDict
from copy import copy
from dataclasses import dataclass
import hashlib
import json
import secrets
import threading
import time
from typing import Protocol

from .model_visible_projection_helpers import docs_context_budget_tokens


@dataclass(frozen=True)
class SourceReference:
    project_root: str
    project_identity: str
    path: str
    content_sha256: str
    catalog_entry_hash: str
    authority: str
    scope: str
    module_path: str | None
    line_end: int


class SourceReadGateway(Protocol):
    def authorize(self, reference: SourceReference) -> str | None:
        """Return a typed failure before reading any source text, or None."""
        ...

    def read_snapshot(self, reference: SourceReference) -> bytes:
        """Read bounded source bytes without following links or using the network."""
        ...


@dataclass(frozen=True)
class _Cursor:
    reference: SourceReference
    start: int
    remaining_reads: int
    expires: float
    end: int | None = None


class SourceContinuationReader:
    """Session-local opaque cursors with fixed budgets and no latest fallback.

    Issuance is an application operation for already selected evidence. The host
    must request a read only for a concrete missing fact. Merely issuing a URI
    performs no hydration. Expiry or restart safely makes a reference unavailable.
    """

    uri_prefix = "docatlas://source/"
    max_tokens = 600
    max_lines = 40
    max_reads = 2
    max_references = 128
    retention_seconds = 600

    def __init__(self, gateway: SourceReadGateway, *, clock=time.monotonic):
        self.gateway = gateway
        self.clock = clock
        self._cursors: OrderedDict[str, _Cursor] = OrderedDict()
        self._lock = threading.RLock()
        from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
        self.minimal = minimal_context_enabled()
        if self.minimal:
            self.uri_prefix = "docatlas://source/v2/"
        # Session tombstones prevent deterministic packet rebinding from reviving
        # consumed or expired capabilities. They contain no source text.
        self._spent: set[str] = set()
        self._issuance_nonce = secrets.token_hex(16)
        self._issuances: dict[str, tuple[int, str]] = {}
        self._registration_only = False

    def registration_snapshot(self) -> SourceContinuationReader:
        """Replay issuance with live authorization but no session mutations.

        The clock, gateway and host limits stay the same. Immutable cursors can
        be shared, while the registry and its lock must be independent: replay
        must neither revive consumed references nor evict the client's cursors.
        This copy is only for binding replayed packets, never resource reads.
        """
        with self._lock:
            snapshot = copy(self)
            snapshot._cursors = OrderedDict(self._cursors)
            snapshot._lock = threading.RLock()
            snapshot._spent = set(self._spent)
            snapshot._issuances = dict(self._issuances)
            snapshot._registration_only = True
        return snapshot

    def fresh_locator(self, canonical: str) -> str:
        """Resolve only on an atomic staging reader after host fresh authorization.

        This is identity allocation, not authorization: issue/issue_range must
        still validate the exact reference and preserve active budgets/expiry.
        """
        with self._lock:
            self._expire()
            ordinal, latest = self._issuances.get(canonical, (0, canonical))
            if latest in self._cursors or latest not in self._spent:
                return latest
            while True:
                ordinal += 1
                material = json.dumps([self._issuance_nonce, canonical, ordinal])
                uri = self.uri_prefix + hashlib.sha256(material.encode()).hexdigest()[:24]
                if uri not in self._cursors and uri not in self._spent:
                    self._issuances[canonical] = (ordinal, uri)
                    return uri

    def issue(self, reference: SourceReference, *, uri: str | None = None) -> str | None:
        if type(reference.line_end) is not int or reference.line_end < 1 or self.gateway.authorize(reference):
            return None
        with self._lock:
            self._expire()
            if uri is not None:
                if self.minimal and uri in self._spent:
                    return None
                if not uri.startswith(self.uri_prefix) or len(uri) != len(self.uri_prefix) + 24:
                    return None
                existing = self._cursors.get(uri)
                if existing is not None:
                    if (existing.reference != reference
                            or existing.start != reference.line_end + 1
                            or existing.end is not None):
                        return None
                    # Re-publication must not mutate a capability already given
                    # to the client, including its original expiry/read budget.
                    return uri
                self._cursors[uri] = _Cursor(reference, reference.line_end + 1, self.max_reads,
                                             self.clock() + self.retention_seconds)
                while not self.minimal and len(self._cursors) > self.max_references:
                    self._cursors.popitem(last=False)
                return uri
            return self._issue_cursor(_Cursor(
                reference, reference.line_end + 1, self.max_reads,
                self.clock() + self.retention_seconds,
            ))

    def issue_range(
        self, reference: SourceReference, *, line_start: int, line_end: int,
        uri: str | None = None,
    ) -> str | None:
        """Register one authorized bounded interval without exposing range params."""
        if (
            type(line_start) is not int or type(line_end) is not int
            or line_start < 1 or line_end < line_start
            or type(reference.line_end) is not int or reference.line_end < 1
            or self.gateway.authorize(reference)
        ):
            return None
        cursor = _Cursor(
            reference, line_start, self.max_reads,
            self.clock() + self.retention_seconds, line_end,
        )
        with self._lock:
            self._expire()
            if uri is None:
                return self._issue_cursor(cursor)
            if not uri.startswith(self.uri_prefix) or len(uri) != len(self.uri_prefix) + 24:
                return None
            if self.minimal and uri in self._spent:
                return None
            existing = self._cursors.get(uri)
            if existing is not None:
                if (
                    existing.reference != reference
                    or existing.start != line_start
                    or existing.end != line_end
                ):
                    return None
                # Idempotent binding must not refresh expiry or read budget.
                return uri
            self._cursors[uri] = cursor
            while not self.minimal and len(self._cursors) > self.max_references:
                self._cursors.popitem(last=False)
            return uri

    def _issue_cursor(self, cursor: _Cursor) -> str:
        uri = self.uri_prefix + secrets.token_hex(12)
        self._cursors[uri] = cursor
        while not self.minimal and len(self._cursors) > self.max_references:
            self._cursors.popitem(last=False)
        return uri

    def _expire(self) -> None:
        if self.minimal:
            for uri, cursor in list(self._cursors.items()):
                if self.clock() >= cursor.expires:
                    self._spent.add(uri)
                    del self._cursors[uri]

    def has_reference(self, uri: str) -> bool:
        with self._lock:
            self._expire()
            return uri in self._cursors

    def retain_references(self, uris: list[str]) -> None:
        """Protect already issued members of a bounded selection from eviction.

        Do this for the whole selected batch before issuing missing references.
        Moving cache entries changes neither their expiry nor remaining reads;
        it also performs no source read or authorization. The caller still has
        to authorize every issued reference and fit the batch to max_references.
        """
        with self._lock:
            for uri in dict.fromkeys(uris):
                if uri in self._cursors:
                    self._cursors.move_to_end(uri)

    def read(self, uri: str) -> dict:
        with self._lock:
            # Consumption also prevents concurrent reads of the same range.
            cursor = self._cursors.pop(uri, None)
            if self.minimal and cursor is not None:
                self._spent.add(uri)
        if cursor is None or self.clock() >= cursor.expires:
            return self._failure("source_unavailable", "unknown_or_expired_reference")
        reference = cursor.reference
        failure = self.gateway.authorize(reference)
        if failure:
            return self._failure(failure, "source_policy_or_snapshot_changed")
        try:
            raw = self.gateway.read_snapshot(reference)
        except (OSError, ValueError):
            return self._failure("source_unavailable", "snapshot_read_failed")
        if "sha256:" + hashlib.sha256(raw).hexdigest() != reference.content_sha256:
            return self._failure("source_changed", "snapshot_digest_mismatch")
        # Revalidate in case catalog/index authority changed during the read.
        failure = self.gateway.authorize(reference)
        if failure:
            return self._failure(failure, "source_policy_or_snapshot_changed")
        try:
            text = raw.decode("utf-8")
            lines = text.splitlines(keepends=self.minimal)
        except UnicodeDecodeError:
            return self._failure("source_unavailable", "unsupported_encoding")
        target_end = min(len(lines), cursor.end) if cursor.end is not None else len(lines)
        if cursor.start > target_end:
            return {"status": "complete", "reason_code": "end_of_source"}
        if self.minimal:
            return self._read_structural(cursor, text, lines, target_end)
        stop = min(target_end, cursor.start + self.max_lines - 1)
        next_uri = self.uri_prefix + secrets.token_hex(12)
        while stop >= cursor.start:
            more = stop < target_end
            continuation = next_uri if more and cursor.remaining_reads > 1 else None
            result = {
                "status": "truncated" if more else "complete",
                "path": reference.path,
                "project_identity": reference.project_identity,
                "content_sha256": reference.content_sha256,
                "line_start": cursor.start,
                "line_end": stop,
                "snippet": "\n".join(lines[cursor.start - 1:stop]),
                "continuation": continuation,
            }
            if more and not continuation:
                result["reason_code"] = "read_limit_reached"
            if docs_context_budget_tokens(result) <= self.max_tokens:
                if continuation:
                    with self._lock:
                        self._cursors[continuation] = _Cursor(
                            reference, stop + 1, cursor.remaining_reads - 1, cursor.expires,
                            cursor.end,
                        )
                        while len(self._cursors) > self.max_references:
                            self._cursors.popitem(last=False)
                return result
            stop -= 1
        return self._failure("source_unavailable", "line_exceeds_read_budget")

    def _read_structural(self, cursor: _Cursor, text: str, lines: list[str], target_end: int) -> dict:
        from docmancer.core.structured_chunking import parse_markdown_parents
        from docmancer.docs.domain.minimal_context_config import EMERGENCY_TOKENS
        parents = parse_markdown_parents(text, cursor.reference.path)
        parent = next((p for p in parents if p.line_start <= cursor.start <= p.line_end), None)
        start, stop = (parent.line_start, parent.line_end) if parent else (1, len(lines))
        # Include the complete subtree. An old chunk boundary inside a block is
        # expanded rather than silently delivering a severed list/table/fence.
        if parent is not None and parent.level:
            for following in parents[parents.index(parent) + 1:]:
                if following.level <= parent.level:
                    break
                stop = following.line_end
        more = stop < target_end
        continuation = self.uri_prefix + secrets.token_hex(12) if more else None
        reference = cursor.reference
        result = {
            "status": "truncated" if more else "complete",
            "path": reference.path, "project_identity": reference.project_identity,
            "content_sha256": reference.content_sha256,
            "line_start": start, "line_end": stop,
            "snippet": "".join(lines[start - 1:stop]), "continuation": continuation,
        }
        from .model_visible_projection_helpers import canonical_projection_bytes
        from .projection_tokenizer import projection_token_count
        measured = projection_token_count(canonical_projection_bytes(result))
        if measured > EMERGENCY_TOKENS:
            return {"status": "error", "reason_code": "context_emergency_stop",
                    "measured_tokens": measured, "emergency_tokens": EMERGENCY_TOKENS}
        if continuation:
            with self._lock:
                self._cursors[continuation] = _Cursor(reference, stop + 1, 0, cursor.expires, cursor.end)
        return result

    @staticmethod
    def _failure(status: str, reason: str) -> dict:
        return {"status": status, "reason_code": reason}


def source_continuation_uri(project_root: str, source: dict) -> str | None:
    """Prepare a bounded locator only when retrieval carries a file snapshot."""
    digest = source.get('_source_snapshot_sha256')
    catalog = source.get('_source_catalog_hash')
    if (not project_root or not digest or not catalog or not source.get('project_identity')
        or type(source.get('line_end')) is not int or source['line_end'] < 1):
        return None
    material = [project_root, source.get('project_identity'), source.get('path'), digest,
                catalog, source.get('doc_scope'), source.get('module_path'),
                source.get('heading_path'), source.get('line_start'), source.get('line_end')]
    identity = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:24]
    from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
    prefix = "docatlas://source/v2/" if minimal_context_enabled() else SourceContinuationReader.uri_prefix
    return prefix + identity


def attach_source_continuation_locators(payload: dict, snapshot: dict, *, root: str, max_tokens: int) -> None:
    """Attach source-local locators and synchronize their snapshot bindings."""
    from .model_visible_projection import _refresh_estimate
    changed = False
    for source in payload.get('sources') or ():
        bound = snapshot[source['evidence_id']]
        uri = source_continuation_uri(root, bound['source'])
        if not uri or type(source.get('line_end')) is not int:
            continue
        source['source_uri'] = uri
        changed = True
        bound['projected_source']['source_uri'] = uri
        bound['source_uri'] = uri
    # Decoration has no intermediate size-dependent decisions. Serializing the
    # complete preselection pool once per row made full acquisition quadratic.
    # The same final estimate and all per-source bindings are retained.
    if changed:
        _refresh_estimate(payload)


def bind_project_source_continuations(reader, project_root: str, projection: dict, snapshot: dict) -> None:
    """Register selected references, removing unavailable optional locators."""
    retain = getattr(reader, "retain_references", None)
    if callable(retain):
        retain([source['source_uri'] for source in projection.get('sources') or ()
                if source.get('source_uri')])
    for source in projection.get('sources') or ():
        uri = source.get('source_uri')
        if not uri:
            continue
        bound = snapshot[source['evidence_id']]
        original = bound['source']
        reference = SourceReference(
            project_root, source['project_identity'], source['path_or_url'],
            original['_source_snapshot_sha256'], original['_source_catalog_hash'],
            source['authority'], source['scope'], original.get('module_path'), source['line_end'],
        )
        if reader.issue(reference, uri=uri) is None:
            source.pop('source_uri', None)
            bound['projected_source'].pop('source_uri', None)
            bound.pop('source_uri', None)
