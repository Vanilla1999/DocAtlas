"""Original mixed-language query remains unchanged; only inspection is enabled."""
import json

from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from docmancer.mcp.docs_server import read_docs_resource


