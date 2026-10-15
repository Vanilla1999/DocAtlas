"""Direct legacy compilers must not manufacture semantics or answer authority."""
from dataclasses import FrozenInstanceError, fields
from hashlib import sha256

import pytest

from eval.task_level.literal_contract_reduction import (
    adapter_pairs, adapter_variants, selected_inputs,
)

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


def _assert_frozen(value, field, replacement, guard):
    try:
        setattr(value, field, replacement)
    except FrozenInstanceError:
        return
    assert False, guard


def _assert_invalid_span(constructor):
    try:
        constructor()
    except ValueError:
        return
    assert False, 'literal_invalid_span_dto'






_SEMANTIC_PAIRS = adapter_pairs(
    [name for name in semantics.__all__ if name.startswith('match_')], QUESTIONS[:15],
)
_SURFACE_PAIRS = adapter_pairs(surfaces.__all__, QUESTIONS[:15])





















