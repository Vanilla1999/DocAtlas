"""Original unanswered questions through the real index and public handler."""
import pytest

from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol, registry_for
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context


