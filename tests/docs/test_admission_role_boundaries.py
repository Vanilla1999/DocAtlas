"""Role recognition must distinguish a description from a declared name."""
import pytest
from docmancer.docs.domain.query_reference_binding import query_mentions
from docmancer.docs.domain.query_terms import query_constraint_roles


@pytest.mark.parametrize('question,connector', [
    ('Can a task function for QueueTasks be normal def?', 'for'),
    ('Can a class with callbacks be async?', 'with'),
    ('What does a function without retries return?', 'without'),
    ('Can a function in the worker return a value?', 'in'),
    ('How is a function from another module called?', 'from'),
    ('Что делает функция для обработки очереди?', 'для'),
    ('Как работает функция с повторными попытками?', 'с'),
    ('Что делает функция без аргументов?', 'без'),
    ('Как работает функция в обработчике?', 'в'),
    ('Как работает метод из другого модуля?', 'из'),
])
def test_descriptive_complement_does_not_declare_a_symbol(question, connector):
    # Removing the occurrence-level grammar check must break this assertion.
    assert connector not in query_constraint_roles(question).hard_exact
    assert not any(m.text.casefold() == connector and m.syntax_role == 'symbol_identity'
                   for m in query_mentions(question))


@pytest.mark.parametrize('name', ['for', 'with', 'without', 'in', 'для', 'с', 'без'])
@pytest.mark.parametrize('quote', ['`', '"'])
def test_explicit_literal_keeps_identity_and_original_offsets(name, quote):
    question = f'Что возвращает function {quote}{name}{quote}?'
    assert name in query_constraint_roles(question).hard_exact
    mention = next(m for m in query_mentions(question) if m.text == name)
    assert mention.syntax_role == 'symbol_identity'
    assert question[mention.start:mention.end] == name


@pytest.mark.parametrize('name', ['worker.run', 'with_retries', 'QueueЖук.run', '--with', 'for.run'])
def test_technical_names_are_not_grammatical_complements(name):
    question = f'What does the function {name} return?'
    assert name.casefold() in query_constraint_roles(question).hard_exact


def test_repeated_spelling_is_classified_per_occurrence():
    question = 'Does a function for QueueTasks call the function `for`?'
    mentions = [m for m in query_mentions(question) if m.text == 'for']
    identities = [m for m in mentions if m.syntax_role == 'symbol_identity']
    assert len(identities) == 1
    assert identities[0].start == question.rindex('for')
    assert 'queuetasks' in query_constraint_roles(question).hard_exact


def test_independent_real_symbol_survives_russian_complement():
    roles = query_constraint_roles('Может ли task function для BackgroundTasks быть обычной def?')
    assert 'для' not in roles.hard_exact
    assert 'backgroundtasks' in roles.hard_exact


def test_punctuation_inside_quotes_is_literal_not_sentence_grammar():
    question = 'What does the function `для?` return?'
    mention = next(m for m in query_mentions(question) if m.text == 'для?')
    assert mention.syntax_role == 'symbol_identity'
    assert question[mention.start:mention.end] == 'для?'
