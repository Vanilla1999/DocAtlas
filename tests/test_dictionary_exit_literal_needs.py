"""Literal root context must not become semantic interpretation or proof."""
from dataclasses import FrozenInstanceError, asdict, replace
from hashlib import sha256

import pytest

from docmancer.docs.application.need_context_disposition import classify_need_context
from docmancer.docs.domain.evidence_set_types import SourceKey
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import (
    CatalogSource, ScopeKey, resolve_references,
)
from docmancer.docs.domain.question_retrieval_needs import retrieval_needs


QUESTIONS = (
    '  If `Client.send` fails, which exception is raised? What is its default?\n',
    'Если `Client.send` завершится ошибкой, что произойдёт? Каково значение по умолчанию?',
    'Compare `Client.send` and `Client.read` when preview is disabled; explain both.',
    'Сравни `Client.send` и `Client.read`, только если режим отключён; объясни оба.',
    'List three categories of `Client.send`; explain each and then configure it.',
    'Перечисли три категории `Client.send`; объясни каждую, затем настрой её.',
    'Why is this required? How is it configured? Which prerequisites apply?',
    'Почему это требуется? Как это настроено? Какие условия необходимы?',
    'ordinary question with no literal identity',
    '\tВопрос без технических символов.\r\n',
)
SCOPE = ScopeKey('literal-project', 'v1', 'literal-snapshot')


def plan(question):
    return resolve_references(question, catalog=(), scope=SCOPE)
















def prepared_context(question, body, path='docs/Client.send.md'):
    digest = sha256(body.encode()).hexdigest()
    source = CatalogSource('guide', SCOPE, path, digest)
    references = resolve_references(question, catalog=(source,), scope=SCOPE)
    contract = compile_need_contracts(question, references)[0]
    key = SourceKey(SCOPE, source.document_id, source.canonical_path, digest)
    candidate = {'source_class': 'project_doc', 'project_identity': SCOPE.project_id,
        'resolved_version': SCOPE.version, 'generation_id': SCOPE.snapshot_id,
        'path_or_url': source.canonical_path, 'char_span': [0, len(body)],
        'snippet': body, 'authority': 'source_of_truth',
        '_reference_root_plan': asdict(references),
        '_reference_plans': {question: asdict(references)},
        '_reference_evidence': {'schema_version': 1, 'source': asdict(source),
            'raw_document': body, 'text': body, 'char_start': 0, 'char_end': len(body), 'owner': None}}
    return contract, {'reference_plan': references, 'candidate': candidate,
        'bundles': (), 'prepared_sources': {key: {'source': asdict(source), 'raw_document': body}}}










def quoted_stem_plan(question):
    catalog = CatalogSource('guide', SCOPE, 'docs/Guide.md', 'a' * 64)
    return resolve_references(question, catalog=(catalog,), scope=SCOPE)







