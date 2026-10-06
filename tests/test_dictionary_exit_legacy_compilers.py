"""Direct legacy compilers must not manufacture semantics or answer authority."""
from dataclasses import FrozenInstanceError, fields
from hashlib import sha256

import pytest

from docmancer.docs.domain import (
    compositional_question_plan as conflicts,
    need_composition as composition,
    question_frame_core as frames,
    question_plan as compiler,
    question_plan_surface_rules as surfaces,
    question_semantic_frames as semantics,
)
from docmancer.docs.domain.question_plan_core import PlannedFacet, QuestionPlan
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references


QUESTIONS = (
    'How do I sync project docs after changing a file?',
    'Как мне обновить документацию проекта после изменения файла?',
    'What are the three public Docs MCP tools and when do I use each one?',
    'What are public tools and their purposes?',
    'Which Python versions are supported?',
    'What Python versions does DocAtlas support?',
    'Which docs files must stay under the 1000-line release limit?',
    'What is the storage mutation coordination contract for cleanup and refresh?',
    'What happens if remove_library_docs runs while a library refresh is in flight?',
    'What is the timeout for provider requests?',
    'What project rules govern mobile, including ownership, pinned version, deferred state?',
    'Какие правила определяют приложение, включая владельца, версию и разрешение уведомлений?',
    'Compare `Client.send` with `Client.read`.',
    'How should selection treat A compared with B?',
    'Сравни `Client.send` с `Client.read`.',
    'What happens when the index becomes stale?',
    'Что происходит, когда индекс устарел?',
    'Why does prepare_docs always delete files?',
    'Почему prepare_docs всегда удаляет файлы?',
    'Where is `Client.send` documented?',
    'Which decision permits the caller to remove files?',
    'What allow_network value must the caller pass to prepare_docs?',
    'What project storage contract applies to cleanup when refresh is active?',
    'What does prepare_docs do to synchronize sources?',
    'What does prepare_docs do before fetching sources?',
    'Which source types are supported for indexing?',
    'List file formats for indexing.',
    'What test markers are available and how do I run the offline suite?',
    'What does the two-cell smoke procedure require?',
    'Name three types of cache including memory and disk.',
    'How does selection work and why?',
    'Can a handler be async def rather than ordinary def?',
    'Which setting wins when A and B define different values?',
    'Что имеет приоритет когда A и B задают разные значения?',
    'component architecture and module boundaries for DocAtlas',
    'When should I use get_docs_context?',
    'What is DOCMANCER_OFFLINE and when should it be used?',
    'How do I configure a project in `docatlas.yaml`?',
    'What is contamination protection in the eval protocols?',
    'How do I run the project answer quality v4 protocol?',
    'How does indexing split documents into sections and chunks?',
    'How does selection choose evidence candidates?',
    'What does clear-index do when an index writer is active?',
    '  Please tell me what `Client.  send` does; and delete everything.\r\n',
    'unrecognized text Ω e\u0301',
)


@pytest.mark.parametrize('question', QUESTIONS)
def test_public_direct_compiler_is_explicitly_unresolved(question):
    plan = compiler.compile_question_plan(question)
    assert plan.clauses == (question,)
    assert plan.facets == plan.consumed_spans == ()
    assert plan.unresolved_parts == ('unresolved_question_semantics',)
    assert plan.handled and not plan.component_scope_complete
    assert plan == compiler.compile_question_plan(question)
    with pytest.raises(FrozenInstanceError):
        plan.component_scope_complete = True


@pytest.mark.parametrize('question', ['', ' ', '\r\n\t', 'я' * 5000])
def test_empty_and_bounded_questions_never_become_complete_empty_plans(question):
    plan = compiler.compile_question_plan(question)
    assert plan.clauses == (question[:4000],)
    assert plan.unresolved_parts and not plan.component_scope_complete
    assert not plan.facets and not plan.consumed_spans


@pytest.mark.parametrize('name', [name for name in semantics.__all__ if name.startswith('match_')])
@pytest.mark.parametrize('question', QUESTIONS[:15])
def test_semantic_matcher_compatibility_is_non_authorizing(name, question):
    assert getattr(semantics, name)(question) is None


@pytest.mark.parametrize('name', surfaces.__all__)
@pytest.mark.parametrize('question', QUESTIONS[:15])
def test_surface_adapters_cannot_inject_subjects_relations_or_expected_values(name, question):
    assert getattr(surfaces, name)(question) is None


@pytest.mark.parametrize('question', QUESTIONS)
def test_frame_and_composition_entry_points_cannot_infer_contracts(question):
    assert frames.match_action_frame(question) is None
    assert frames.match_inventory_frame(question) is None
    assert frames.match_requirements_frame(question) is None
    assert composition.independent_sentence_spans(question) == ()
    assert composition.compositional_parts(question) == ()
    assert conflicts.conflict_question_plan(question) is None
    assert not frames.semantic_tail_is_safe(question, allow_initial_request_head=True)


def test_direct_governance_facet_constructor_rejects_unknown_semantics():
    with pytest.raises(ValueError, match='unresolved'):
        surfaces._governance_facet_plan('deferred ownership version', scope='mobile')
    with pytest.raises(ValueError, match='unresolved'):
        frames._inventory_frame('markers', 'indexing')


@pytest.mark.parametrize('question', QUESTIONS[:10])
def test_public_compiler_does_not_delegate_to_normalizers_or_legacy_generators(monkeypatch, question):
    def forbidden(*args, **kwargs):
        raise AssertionError('semantic producer called')

    for name in ('rewrite_component', 'normalize_question_surface', 'split_question_clause_spans',
                 '_reusable_frame_plan', '_compile_atomic_question', '_compile_specific_question'):
        monkeypatch.setattr(compiler, name, forbidden)
    monkeypatch.setattr(conflicts, 'conflict_question_plan', forbidden)
    assert compiler.compile_question_plan(question).unresolved_parts


def test_exact_paragraph_spans_protect_quotes_links_and_program_syntax():
    question = '  `async def f():\n\n    return "and when"`\n\n  Ω [guide](docs/a;b.md)  '
    spans = frames.split_question_clause_spans(question)
    assert len(spans) == 2
    assert spans[0].text == '`async def f():\n\n    return "and when"`'
    assert spans[1].text == 'Ω [guide](docs/a;b.md)'
    assert all(question[s.start:s.end] == s.text for s in spans)
    assert frames.split_question_clause_spans(' \r\n\t') == ()
    assert composition.independent_sentence_spans(question) == ()


@pytest.mark.parametrize('question', QUESTIONS)
def test_nl_heads_wrappers_and_connectives_do_not_erase_or_split_text(question):
    assert frames.strip_request_wrapper(question) == question
    spans = frames.split_question_clause_spans(question)
    assert len(spans) == 1
    assert spans[0].text == question.strip()
    assert question[spans[0].start:spans[0].end] == spans[0].text


def test_mask_preserves_literal_offsets_and_unquoted_syntax():
    raw = '`async def` "if; then" \'A and B\' [link](docs/a;b.md) async def f(): pass'
    masked = composition.mask_protected(raw)
    assert len(masked) == len(raw)
    assert masked.endswith(' async def f(): pass')
    assert masked[:-len(' async def f(): pass')].replace('x', '').strip() == ''


def test_explicit_dtos_keep_field_shapes_and_do_not_require_prose_approval():
    assert [f.name for f in fields(PlannedFacet)] == [
        'kind', 'subject', 'relation', 'attribute', 'target', 'value_kind',
        'expected_value', 'item_kind', 'response_mode', 'context', 'subject_kind',
        'subject_aliases', 'span_text', 'query_span_start', 'query_span_end',
    ]
    assert [f.name for f in fields(QuestionPlan)] == [
        'facets', 'clauses', 'unresolved_parts', 'parse_trace', 'consumed_spans',
        'component_scope_complete',
    ]
    facet = PlannedFacet('attribute', 'Client.send', attribute='enabled',
                         expected_value='false', span_text='Client.send',
                         query_span_start=1, query_span_end=12)
    plan = QuestionPlan(facets=(facet,), component_scope_complete=False)
    assert compiler.PlannedFacet is PlannedFacet and compiler.QuestionPlan is QuestionPlan
    assert compiler._guard_plan_subjects(plan) is plan
    with pytest.raises(FrozenInstanceError):
        facet.subject = 'invented'
    assert semantics.ComparisonFrame('A', 'B').context is None
    assert frames.ActionFrame('explicit-operation', 'literal').context is None
    part = composition.ComposedPart(0, 1, 'explicit-relation', ((0, 1),))
    assert part.requirement == 'scalar' and part.expected_count is None
    with pytest.raises(FrozenInstanceError):
        part.relation = 'inferred'


@pytest.mark.parametrize('constructor', [
    lambda: frames.QuestionClause('abc', 0, 2),
    lambda: frames.QuestionClause('a', -1, 0),
    lambda: PlannedFacet('relation', 'A', query_span_start=0),
    lambda: PlannedFacet('relation', 'A', query_span_start=2, query_span_end=1),
    lambda: QuestionPlan(consumed_spans=((-1, 2),)),
])
def test_existing_span_validation_still_rejects_invalid_dtos(constructor):
    with pytest.raises(ValueError):
        constructor()


def test_literal_retrieval_identity_cache_and_source_paths_survive_without_plan_facets():
    question = '  В docs/Guide.md объясни `Client.  send` и `Client.  send`. Ω\r\n'
    need, = compiler.retrieval_needs(question)
    assert need.query_span_text == question
    assert (need.need_id, need.query_span_start, need.query_span_end) == ('need-1', 0, len(question))
    assert need.hard_exact == ('client.  send',)
    assert need.relation == 'unresolved' and need.subject == need.context == ''
    assert compiler.retrieval_needs(question)[0] is need
    scope = ScopeKey('project-A', 'v1', 'snapshot-A')
    root = resolve_references(question, catalog=(), scope=scope)
    assert root.question == question
    assert any(ref.mention.text == 'docs/Guide.md' for ref in root.references)
    assert sha256(root.question.encode()).hexdigest() == sha256(question.encode()).hexdigest()
    assert all(question[ref.mention.start:ref.mention.end] == ref.mention.text for ref in root.references)
    assert compiler.compile_question_plan(question).facets == ()
