"""Retention preferences do not certify answers or bypass source guards."""
from copy import deepcopy

import pytest

from docmancer.docs.domain.context_hint_policy import preserves_unresolved_context_candidate
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from tests.evidence_quality_v2.test_readme_neutral_context import TEXT, CASES, capture
from tests.test_named_document_context_integration import _named_document_service


