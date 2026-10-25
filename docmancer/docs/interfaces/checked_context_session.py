"""Managed MCP session plus an explicitly consented semantic-model checker.

No provider is selected implicitly. The base session remains provider-neutral.
The checker sees only model_input(), after source selection, packet budgets and
history deduplication. Verdicts never enter source authority or MCP metadata.
"""
from __future__ import annotations
from copy import deepcopy

from docmancer.docs.application.semantic_sufficiency import canonical, fingerprint
from .model_context_session import ModelContextSession, ModelSessionError


class CheckedContextSession(ModelContextSession):
    def __init__(self, client, *, checker, max_checks=2, **kwargs):
        if not callable(getattr(checker, "assess", None)):
            raise TypeError("explicit_semantic_checker_required")
        if type(max_checks) is not int or not 1 <= max_checks <= 4:
            raise ValueError("invalid_semantic_check_budget")
        super().__init__(client, **kwargs)
        self._checker, self._max_checks = checker, max_checks
        self._checks = []
        self._assessment = None

    @property
    def semantic_audit(self):
        """Private bound decisions, not additional model-context history."""
        return deepcopy(self._checks)

    def invalidate(self):
        super().invalidate()
        self._assessment = None

    async def _retrieve_request(self, **kwargs):
        self._assessment = None
        return await super()._retrieve_request(**kwargs)

    async def _language_request(self, *, refresh):
        if refresh:
            self._assessment = None
        return await super()._language_request(refresh=refresh)

    def assessment(self):
        if self._pending:
            raise ModelSessionError("session_operation_in_progress")
        if self._assessment is None:
            return None
        current = fingerprint(canonical(self.model_input()))
        if (self._assessment["epoch"] != self._epoch or
                self._assessment["verdict"]["final_context_sha256"] != current):
            self._assessment = None
            return None
        return deepcopy(self._assessment["verdict"])

    async def assess(self):
        async with self._lock:
            cached = self.assessment()
            if cached is not None:
                return cached
            if len(self._checks) >= self._max_checks:
                raise ModelSessionError("semantic_check_limit")
            context = self.model_input()
            epoch, wire = self._epoch, canonical(context)
            # Do not reinterpret a source/permission/transport failure as absence.
            all_events = [context.get("result_context") or {}, *(context.get("results") or [])]
            if any(event.get("error") or event.get("result") or event.get("hard_stop") or
                   event.get("requires_confirmation") or
                   (event.get("delivery_decision") or {}).get("deliverable") is False for event in all_events):
                raise ModelSessionError("semantic_check_blocked_by_delivery")
            record = {"epoch": epoch, "final_context_sha256": fingerprint(wire), "status": "attempted"}
            self._checks.append(record)
            self._pending = True
            try:
                verdict = await self._checker.assess(question=self._question, final_context_json=wire)
            except BaseException as exc:
                record.update(status="error", error_type=type(exc).__name__)
                raise
            finally:
                self._pending = False
            if epoch != self._epoch:
                record.update(status="discarded", reason="session_invalidated_during_check")
                raise ModelSessionError("session_invalidated_during_check")
            if (not isinstance(verdict, dict) or verdict.get("final_context_sha256") != fingerprint(wire)
                    or verdict.get("question_sha256") != fingerprint(self._question)
                    or verdict.get("status") not in {"sufficient", "partial", "insufficient", "unknown"}
                    or verdict.get("authority") != "none"):
                record.update(status="invalid", reason="unbound_semantic_verdict")
                raise ModelSessionError("unbound_semantic_verdict")
            record.update(status="completed", verdict=deepcopy(verdict))
            self._assessment = {"epoch": epoch, "verdict": deepcopy(verdict)}
            return deepcopy(verdict)
