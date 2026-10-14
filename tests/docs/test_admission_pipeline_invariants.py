"""Current source/body witnesses must survive only real same-scope evidence."""
from copy import deepcopy
from pathlib import Path
import socket

import pytest

from docmancer.docs.application.docs_context_projection import _requalify_visible_source
from tests.docs._current_source_guard_fixtures import (
    capture_source_case, source_binding, assert_visible_fact, source_contains_fact,
)
from tests.docs.test_admission_guard_composition import QUESTION, FACT


@pytest.fixture
def indexed_source(tmp_path):
    cap = capture_source_case(tmp_path, {'Guide.md': '# Settings\n\n' + FACT}, QUESTION, lookups=(FACT,))
    public, original, _ = source_binding(cap, 'Guide.md', FACT)
    raw = deepcopy(original)
    return {
        **raw, 'path_or_url': public['path_or_url'], 'snippet': public['snippet'],
        '_qualification_candidate': raw,
        '_expected_project_identity': public['project_identity'],
    }


def requalify(source):
    return _requalify_visible_source(source, query_text={
        'query-original': QUESTION, 'query-lookup-1': FACT,
    })


def recheck(source):
    return requalify(source)['retrieval_query_matches']['query-lookup-1']
