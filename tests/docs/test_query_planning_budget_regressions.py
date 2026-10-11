"""Optional lookup hygiene must reach the actual application lookups."""
from types import SimpleNamespace
import pytest
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
