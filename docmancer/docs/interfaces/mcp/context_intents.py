"""Explicit project request intents; no language-based routing defaults."""
from typing import Any

from docmancer.docs.domain.mutation_intent import MutationIntentContract, build_mutation_intent


class InvalidContextIntent(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def normalize_context_intents(
    args: dict[str, Any], question: str,
) -> tuple[str, str | None, bool, MutationIntentContract]:
    request = args.get("request_intent")
    lifecycle = args.get("lifecycle_intent")
    if request is not None and request not in ("read", "change"):
        raise InvalidContextIntent("invalid_request_intent", "request_intent must be read or change")
    if lifecycle is not None and lifecycle not in ("current", "historical", "either"):
        raise InvalidContextIntent("invalid_lifecycle_intent", "lifecycle_intent must be current, historical or either")
    project_only = bool(args.get("project_path")) and not args.get("library") and not args.get("libraries")
    if request is not None and not project_only:
        raise InvalidContextIntent("invalid_request_intent_scope", "request_intent requires project-only context")
    if lifecycle is not None and not project_only:
        raise InvalidContextIntent("invalid_lifecycle_scope", "lifecycle_intent requires project-only context")
    request = request or "read"
    if project_only:
        lifecycle = lifecycle or "current"
    mutation = (MutationIntentContract(operation="none", artifact_kind="unknown", requested_targets=())
                if request == "read" else build_mutation_intent(question))
    return request, lifecycle, project_only, mutation
