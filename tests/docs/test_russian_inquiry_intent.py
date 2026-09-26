"""Russian factual inquiries must not become edit requests; real edits remain routed."""
import pytest

from docmancer.docs.domain.request_intent import find_change_clause, is_change_request


@pytest.mark.parametrize("question", [
    "Удаляет ли clear-index --scope global пользовательскую конфигурацию вместе с производными индексами?",
    "Обновляет ли sync_project_docs индекс?",
    "Изменяет ли команда исходные файлы?",
    "Создаёт ли prepare_docs новые документы?",
    "Добавляет ли установка новую конфигурацию?",
    "Переименовывает ли синхронизация файлы?",
    "Удалить ли старый индекс?",
    "  УДАЛЯЕТ ЛИ команда конфигурацию?",
    "- Обновляет\tли команда индекс?",
    "Создаёт ли команда каталог?",
    "Описание операции. Удаляет ли она конфигурацию?",
])
def test_russian_inquiry_is_not_a_change_imperative(question):
    assert find_change_clause(question) is None
    assert is_change_request(question) is False


@pytest.mark.parametrize("question", [
    "Удали docs/old.md.",
    "Удалите docs/old.md.",
    "Удалить docs/old.md.",
    "Пожалуйста исправь обработчик.",
    "Обнови конфигурацию.",
    "Создай файл.",
    "Исправь эту ошибку, пожалуйста?",
    "Удали линию из файла.",
    "Delete docs/old.md.",
    "Fix the handler, please?",
    "Удали `old.md` и объясни, удаляет ли команда кэш.",
])
def test_actual_imperatives_remain_change_requests(question):
    assert is_change_request(question) is True


def test_inquiry_does_not_hide_later_explicit_imperative():
    question = "Удаляет ли команда индекс? Исправь src/cache.py."
    clause = find_change_clause(question)
    assert clause is not None
    assert clause.verb == "Исправь"
    assert clause.verb_start == question.index("Исправь")
    assert question[clause.verb_start:clause.verb_end] == "Исправь"


@pytest.mark.parametrize("question", [
    'Пример: "Удали docs/old.md." Удаляет ли команда индекс?',
    "```text\nУдали docs/old.md.\n```\nОбновляет ли команда кэш?",
    "`Удали old.md` — пример. Создаёт ли команда новый файл?",
])
def test_quoted_edit_examples_do_not_override_inquiry(question):
    assert is_change_request(question) is False
