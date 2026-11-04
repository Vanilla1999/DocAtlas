"""Step-3 research flags stay opt-in, validated and dictionary-free."""
from __future__ import annotations

import importlib

import pytest

from docmancer.docs.application import joint_context_selection as selection
from docmancer.retrieval.lexical_terms import character_ngrams


def test_character_ngrams_span_words_and_keep_counts():
    assert character_ngrams("Флаг") == (" фла", "флаг", "лаг ")
    assert character_ngrams("a b") == (" a b", "a b ")
    assert character_ngrams("") == ()
    assert character_ngrams("to be to")[:4] == (" to ", "to b", "o be", " be ")


def test_character_ngrams_match_inflections_without_a_dictionary():
    left, right = set(character_ngrams("окружении")), set(character_ngrams("окружения"))
    assert {"окру", "круж", "руже", "ужен"} <= left & right
    assert set(character_ngrams("manage")) & set(character_ngrams("manages")) >= {"mana", "anag", "nage"}


@pytest.mark.parametrize("name", sorted(selection._EXPERIMENT_CHOICES))
def test_joint_selection_flags_default_off_and_reject_unknown(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
    assert selection._experiment(name) == selection._EXPERIMENT_CHOICES[name][0]
    monkeypatch.setenv(name, "unknown")
    with pytest.raises(ValueError, match=name):
        selection._experiment(name)


def test_cost_scale_default_is_square_root_of_bytes():
    assert selection._cost_scale(400, "cost_sqrt") == 20.0
    assert selection._cost_scale(400, "gain") == 1.0


@pytest.mark.parametrize(("name", "value"), [
    ("DOCATLAS_EXPERIMENT_ACQUISITION_SECTIONS", "yes"),
    ("DOCATLAS_EXPERIMENT_ACQUISITION_TERMS", "char5"),
])
def test_acquisition_flags_reject_unknown(monkeypatch, name, value):
    import docmancer.retrieval.experimental_acquisition as acquisition
    monkeypatch.setenv(name, value)
    try:
        with pytest.raises(ValueError, match=name):
            importlib.reload(acquisition)
    finally:
        monkeypatch.delenv(name)
        importlib.reload(acquisition)
    assert acquisition.ACQUISITION_SECTIONS is False
    assert acquisition.ACQUISITION_TERMS == "word"
