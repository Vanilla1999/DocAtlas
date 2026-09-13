"""Bounded source continuation; references never grant additional authority."""
from __future__ import annotations

from collections import OrderedDict
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

    def issue(self, reference: SourceReference, *, uri: str | None = None) -> str | None:
        if type(reference.line_end) is not int or reference.line_end < 1 or self.gateway.authorize(reference):
            return None
        with self._lock:
            if uri is not None:
                if not uri.startswith(self.uri_prefix) or len(uri) != len(self.uri_prefix) + 24:
                    return None
                existing = self._cursors.get(uri)
                if existing and existing.reference != reference:
                    return None
                self._cursors[uri] = _Cursor(reference, reference.line_end + 1, self.max_reads,
                                             self.clock() + self.retention_seconds)
                while len(self._cursors) > self.max_references:
                    self._cursors.popitem(last=False)
                return uri
            return self._issue_cursor(_Cursor(
                reference, reference.line_end + 1, self.max_reads,
                self.clock() + self.retention_seconds,
            ))

    def _issue_cursor(self, cursor: _Cursor) -> str:
        uri = self.uri_prefix + secrets.token_hex(12)
        self._cursors[uri] = cursor
        while len(self._cursors) > self.max_references:
            self._cursors.popitem(last=False)
        return uri

    def has_reference(self, uri: str) -> bool:
        with self._lock:
            return uri in self._cursors

    def read(self, uri: str) -> dict:
        with self._lock:
            # Consumption also prevents concurrent reads of the same range.
            cursor = self._cursors.pop(uri, None)
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
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            return self._failure("source_unavailable", "unsupported_encoding")
        if cursor.start > len(lines):
            return {"status": "complete", "reason_code": "end_of_source"}
        stop = min(len(lines), cursor.start + self.max_lines - 1)
        next_uri = self.uri_prefix + secrets.token_hex(12)
        while stop >= cursor.start:
            more = stop < len(lines)
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
                        )
                        while len(self._cursors) > self.max_references:
                            self._cursors.popitem(last=False)
                return result
            stop -= 1
        return self._failure("source_unavailable", "line_exceeds_read_budget")

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
    return SourceContinuationReader.uri_prefix + identity


def attach_source_continuation_locators(payload: dict, snapshot: dict, *, root: str, max_tokens: int) -> None:
    """Spend only spare DTO budget; never displace an already selected fact."""
    from .model_visible_projection import _refresh_estimate
    for source in payload.get('sources') or ():
        bound = snapshot[source['evidence_id']]
        uri = source_continuation_uri(root, bound['source'])
        if not uri or type(source.get('line_end')) is not int:
            continue
        source['source_uri'] = uri
        _refresh_estimate(payload)
        if docs_context_budget_tokens(payload) > max_tokens:
            source.pop('source_uri')
            _refresh_estimate(payload)
        else:
            bound['projected_source']['source_uri'] = uri
            bound['source_uri'] = uri


def bind_project_source_continuations(reader, project_root: str, projection: dict, snapshot: dict) -> None:
    """Register selected references, removing unavailable optional locators."""
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
