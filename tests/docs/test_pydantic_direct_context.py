"""User-visible regression on pinned upstream docs, without host lookup hints."""
from pathlib import Path

from eval.evidence_quality_v2.run import load_protocol, documents_for
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from docmancer.mcp.docs_server import call_docs_tool_payload

QUESTION = "Перечисли способы включить strict mode, включая field, annotation, config и validation call."


