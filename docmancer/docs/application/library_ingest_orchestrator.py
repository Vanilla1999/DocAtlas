"""Bounded library-ingest job orchestration with injected runtime ports."""

from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
import hashlib
from datetime import datetime, timedelta, timezone
import json
import time
from typing import Any, Callable

from docmancer.docs.fetch_policy import redact_url
from docmancer.docs.models import DocsJobStartResult, DocsTarget, DocsTargetsPrefetchResult, RefreshResult
from docmancer.docs.application.library_ingest_ports import LibraryIngestPorts


class LibraryIngestOrchestrator:
    """Own async lifecycle state while the refresh adapter owns ingest work."""

    def __init__(
        self,
        ports: LibraryIngestPorts,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.ports = ports
        self._monotonic = monotonic
        self._utc_now = utc_now

    @property
    def jobs(self) -> Any:
        return self.ports.jobs

    def prefetch_docs(
        self,
        library: str,
        ecosystem: str | None = None,
        versions: list[str] | None = None,
        docs_url: str | None = None,
        docs_url_template: str | None = None,
        source_type: str | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
        target_plan: list[DocsTarget] | None = None,
    ) -> RefreshResult | DocsTargetsPrefetchResult | DocsJobStartResult:
        # Library names, legacy raw URLs and ceilings do not establish a finite
        # target contract. Never resolve/register guessed sources as a fallback.
        if not target_plan or len(target_plan) != 1 or not isinstance(target_plan[0], DocsTarget):
            return self.unresolved(library, "explicit_target_required")
        target_plan = deepcopy(target_plan)
        target = target_plan[0]
        if (target.library != library
                or (ecosystem is not None and ecosystem != target.ecosystem)
                or (versions is not None and versions != [target.version])
                or (source_type is not None and source_type != target.source_type)
                or (docs_url is not None and docs_url != target.docs_url)
                or (docs_url_template is not None and docs_url_template != target.docs_url_template)):
            return self.unresolved(library, "explicit_target_identity_mismatch")
        if self.ports.prefetch_targets is None:
            return self.unresolved(library, "explicit_target_port_required")
        if not async_:
            result = self.ports.prefetch_targets(
                target_plan,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
            )
            return result if self._known_target_result(result) else self.unresolved(library, "unknown_target_result")

        request_identity = json.dumps(
            {
                "library": library,
                "ecosystem": ecosystem,
                "docs_url": redact_url(docs_url) if docs_url else None,
                "docs_url_template": redact_url(docs_url_template) if docs_url_template else None,
                "versions": versions or [],
                # Redacted URLs alone collide on meaningful query parameters.
                "target_plan_sha256": hashlib.sha256(json.dumps(
                    [asdict(target) for target in target_plan], sort_keys=True,
                    ensure_ascii=False, separators=(",", ":"),
                ).encode("utf-8")).hexdigest(),
            },
            sort_keys=True,
        )
        executor = self.ports.executor()
        if not executor.try_reserve():
            capacity = executor.capacity()
            rejected = self.jobs.create("prefetch_library_docs", request_identity=request_identity, with_generation=False)
            self.jobs.update(
                rejected.job_id,
                status="failed",
                phase="done",
                reason_code="busy",
                retryable=True,
                running_jobs=capacity.running,
                queued_jobs=capacity.queued,
                max_running_jobs=capacity.max_running,
                max_queued_jobs=capacity.max_queued,
                message="Library documentation capacity is full; retry after 2 seconds.",
            )
            return DocsJobStartResult(
                job_id=rejected.job_id,
                status="busy",
                message="Library documentation capacity is full; retry after 2 seconds.",
            )

        try:
            job = self.jobs.create(
                "prefetch_library_docs",
                request_identity=request_identity,
                request_payload={
                    "library": library,
                    "ecosystem": ecosystem,
                    "versions": versions or [],
                    "docs_url": docs_url,
                    "docs_url_template": docs_url_template,
                    "source_type": source_type,
                    "force_refresh": force_refresh,
                    "continue_on_error": continue_on_error,
                    "target_plan": [asdict(target) for target in target_plan or []],
                },
            )
        except Exception:
            executor.release_reservation()
            raise
        deadline_seconds = self.ports.timeout_seconds()
        monotonic_deadline = self._monotonic() + deadline_seconds
        deadline_at = self._utc_now() + timedelta(seconds=deadline_seconds)
        self.jobs.update(
            job.job_id,
            status="pending",
            phase="queued",
            current_target=library,
            message="Queued library docs prefetch job.",
            deadline_at=deadline_at.isoformat(timespec="seconds"),
        )

        def terminalize(reason: str) -> None:
            current = self.jobs.get(job.job_id)
            if current is None or current.status in {"succeeded", "partial", "failed", "cancelled", "interrupted"}:
                return
            if reason == "cancelled":
                self.jobs.update(
                    job.job_id,
                    status="cancelled",
                    phase="done",
                    reason_code="cancelled",
                    retryable=True,
                    message="Library docs prefetch cancelled.",
                )
                return
            self.jobs.append_error(job.job_id, "Library docs prefetch exceeded its configured deadline.")
            self.jobs.update(
                job.job_id,
                status="failed",
                phase="done",
                reason_code="job_deadline_exceeded",
                retryable=True,
                message="Library docs prefetch exceeded its configured deadline.",
            )

        def update_capacity(capacity: Any) -> None:
            self.jobs.update(
                job.job_id,
                queue_position=capacity.queue_position,
                running_jobs=capacity.running,
                queued_jobs=capacity.queued,
                max_running_jobs=capacity.max_running,
                max_queued_jobs=capacity.max_queued,
            )

        try:
            capacity = executor.submit_reserved(
                lambda: self._run_prefetch_docs_job(
                    job.job_id,
                    library,
                    ecosystem,
                    versions,
                    docs_url,
                    docs_url_template,
                    source_type,
                    force_refresh,
                    continue_on_error,
                    monotonic_deadline,
                    target_plan,
                ),
                deadline_at=monotonic_deadline,
                cancelled=lambda: self.jobs.cancellation_requested(job.job_id),
                terminalize=terminalize,
                on_capacity=update_capacity,
            )
        except Exception:
            executor.release_reservation()
            raise
        self.jobs.update(
            job.job_id,
            queue_position=capacity.queue_position,
            running_jobs=capacity.running,
            queued_jobs=capacity.queued,
            max_running_jobs=capacity.max_running,
            max_queued_jobs=capacity.max_queued,
        )
        return DocsJobStartResult(job_id=job.job_id, status="pending", message="Queued library docs prefetch job.")

    def _run_prefetch_docs_job(
        self,
        job_id: str,
        library: str,
        ecosystem: str | None,
        versions: list[str] | None,
        docs_url: str | None,
        docs_url_template: str | None,
        source_type: str | None,
        force_refresh: bool,
        continue_on_error: bool,
        deadline: float,
        target_plan: list[DocsTarget] | None,
    ) -> None:
        initial = self.jobs.get(job_id)
        generation_id = initial.generation_id if initial else None
        if not self.jobs.generation_active(job_id, generation_id):
            return
        if self._monotonic() >= deadline:
            return
        self.jobs.update(
            job_id,
            status="running",
            phase="resolving",
            queue_position=None,
            total_targets=max(len(versions or []), 1),
            current_target=library,
            current_url=docs_url,
            message="Started library docs prefetch job.",
        )
        if hasattr(self.jobs, "append_event"):
            self.jobs.append_event(job_id, {
                "phase": "resolving",
                "message": "Resolving registered library documentation source.",
                "target": library,
                **({"url": docs_url} if docs_url else {}),
            })

        def cancelled() -> bool:
            return (
                not self.jobs.generation_active(job_id, generation_id)
                or self.jobs.cancellation_requested(job_id)
                or self._monotonic() >= deadline
            )

        def begin_commit() -> bool:
            if cancelled():
                return False
            self.jobs.update(job_id, phase="committing", message="Publishing staged library index.")
            return not cancelled()

        try:
            if cancelled():
                if not self.jobs.generation_active(job_id, generation_id):
                    return
                if self.jobs.cancellation_requested(job_id):
                    self._cancel(job_id)
                else:
                    self.jobs.update(job_id, status="failed", phase="done", reason_code="job_deadline_exceeded", retryable=True)
                return
            if target_plan and self.ports.prefetch_targets is not None:
                result = self.ports.prefetch_targets(
                    target_plan,
                    force_refresh=force_refresh,
                    continue_on_error=continue_on_error,
                    job_id=job_id,
                    deadline_at=deadline,
                    should_cancel=cancelled,
                    begin_commit=begin_commit,
                    staging_owner={"job_id": job_id, "generation_id": generation_id or ""},
                )
            else:
                result = self.unresolved(library, "explicit_target_required")
            if not self._known_target_result(result):
                result = self.unresolved(library, "unknown_target_result")
        except Exception as exc:
            if not self.jobs.generation_active(job_id, generation_id):
                return
            if self.jobs.cancellation_requested(job_id):
                self._cancel(job_id)
                return
            self.jobs.append_error(job_id, str(exc))
            self.jobs.update(job_id, status="failed", phase="done", reason_code="indexing_failed", retryable=False, message=str(exc))
            return

        if not self.jobs.generation_active(job_id, generation_id):
            return
        if self.jobs.cancellation_requested(job_id):
            self._cancel(job_id)
            return
        if result.status == "cancelled":
            if self.jobs.cancellation_requested(job_id):
                self._cancel(job_id)
            else:
                self.jobs.append_error(job_id, "Library docs prefetch exceeded its configured deadline.")
                self.jobs.update(job_id, status="failed", phase="done", reason_code="job_deadline_exceeded", retryable=True, message="Library docs prefetch exceeded its configured deadline.")
            return
        failed, succeeded = int(result.targets_failed or 0), int(result.targets_completed or 0)
        status = "partial" if result.status == "partial" else ("succeeded" if failed == 0 else ("partial" if succeeded else "failed"))
        if result.status in {"failed", "needs_docs_url", "aborted"} and not succeeded:
            status = "failed"
        reason_code = self._result_reason_code(result, status)
        retryable = self._result_retryable(result, reason_code)
        failure = result.preindex or {}
        if status in {"failed", "partial"} and result.message:
            self.jobs.append_error(job_id, result.message)
        self.jobs.update(
            job_id,
            status=status,
            phase="done",
            current_target=library,
            total_targets=max(succeeded + failed, 1),
            completed_targets=succeeded,
            failed_targets=failed,
            total_pages=int(result.pages_indexed or 0) + int(result.pages_failed or 0),
            completed_pages=int(result.pages_indexed or 0),
            indexed_pages=int(result.pages_indexed or 0),
            failed_pages=int(result.pages_failed or 0),
            page_failure_summary=list(failure.get("page_failure_summary") or []),
            total_chunks=int(result.chunks_indexed or 0),
            completed_chunks=int(result.chunks_indexed or 0),
            reason_code=reason_code,
            retryable=retryable,
            failure_phase=failure.get("failure_phase"),
            failure_operation=failure.get("failure_operation"),
            exception_type=failure.get("exception_type"),
            exception_message=failure.get("exception_message"),
            exception_traceback=failure.get("exception_traceback"),
            failed_url=failure.get("failed_url"),
            http_status=failure.get("http_status"),
            vector_sync=dict(failure.get("vector_sync") or {}),
            message=result.message or f"Library docs prefetch {status}.",
        )

    def _cancel(self, job_id: str) -> None:
        self.jobs.update(job_id, status="cancelled", phase="done", reason_code="cancelled", retryable=True, message="Library docs prefetch cancelled.")

    @staticmethod
    def unresolved(library: str, reason: str) -> RefreshResult:
        return RefreshResult(
            library_id=None, status="needs_explicit_target", docs_url=None,
            last_refreshed_at=None, targets_failed=1, reason_codes=[reason],
            message=f"{reason}: supply one explicit DocsTarget with selected URLs/files and transport ceilings.",
        )

    @staticmethod
    def _known_target_result(result: Any) -> bool:
        if not isinstance(result, RefreshResult):
            return False
        if result.status in {"updated", "ok", "skipped"}:
            return type(result.targets_completed) is int and result.targets_completed > 0
        return result.status in {"partial", "failed", "cancelled", "needs_docs_url", "needs_explicit_target", "needs_source_manifest", "aborted", "empty_index"}

    @staticmethod
    def _result_reason_code(result: RefreshResult, status: str) -> str:
        if status == "succeeded":
            return "healthy"
        if status == "partial":
            network_codes = {"connect_timeout", "read_timeout", "dns_failure", "tls_failure", "network_unreachable", "http_failure"}
            if code := next((code for code in result.reason_codes if code in network_codes), None):
                return code
            return "partial_failure"
        if result.status == "needs_docs_url":
            return "needs_docs_url"
        return str(result.reason_codes[0] if result.reason_codes else (result.preindex or {}).get("reason_code") or "indexing_failed")

    @classmethod
    def _result_retryable(cls, result: RefreshResult, reason_code: str) -> bool:
        return cls._retryable_reason_code(reason_code) or any(cls._retryable_reason_code(code) for code in result.reason_codes)

    @staticmethod
    def _retryable_reason_code(reason_code: str) -> bool:
        return reason_code in {
            "connect_timeout", "read_timeout", "dns_failure", "tls_failure", "network_timeout",
            "network_unreachable", "network_transport_error", "job_deadline_exceeded", "vector_indexing_failed",
        }
