from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


def _rows(question, intent):
    return [r for r in build_project_retrieval_aliases(question) if r.intent_id == intent]


def test_preparation_error_gets_subject_aware_troubleshooting_probe():
    q = "The documentation preparation task finished with an error. Should I repeat my original question now, or take another step first?"
    rows = _rows(q, "troubleshooting")
    assert len(rows) == 1
    assert rows[0].text == "documentation preparation job status terminal failed docs_status"


def test_ru_no_network_dependency_cache_question_gets_neutral_acquisition_probe():
    q = "Ноутбук не подключён к сети, а документация этой зависимости никогда не кэшировалась. Может ли обычный запрос документации загрузить её?"
    rows = _rows(q, "offline_dependency_acquisition")
    assert len(rows) == 1
    assert rows[0].text == "external dependency documentation normal retrieval network acquisition cache"
    assert _rows(q, "offline_usage")
    assert all(forbidden not in rows[0].text for forbidden in ("cannot", "must", "fetch denied", "ask user"))


def test_plain_offline_question_keeps_generic_probe_and_no_test_bias():
    rows = _rows("How does DocAtlas work in offline mode?", "offline_usage")
    assert rows
    assert rows[0].text.endswith("offline mode")
    assert "test suite" not in " ".join(r.text for r in rows)
    assert not _rows("How does DocAtlas work in offline mode?", "offline_dependency_acquisition")


def _boundary_texts(question):
    return [r.text for r in _rows(question, "documentation_scope_boundary")]


def test_ru_project_vs_external_dependency_docs_gets_diverse_neutral_boundary_probes():
    q = "Чем поиск по собственной документации этого репозитория отличается от поиска по документации внешнего пакета?"
    assert _boundary_texts(q) == [
        "project-owned documentation external dependency documentation different separate",
        "project-owned documentation repository retrieval scope provenance",
        "external dependency documentation retrieval scope provenance",
    ]


def test_en_project_vs_external_dependency_docs_uses_same_boundary_probes():
    q = "How is searching this repository's own documentation different from searching an external package's documentation?"
    assert _boundary_texts(q) == [
        "project-owned documentation external dependency documentation different separate",
        "project-owned documentation repository retrieval scope provenance",
        "external dependency documentation retrieval scope provenance",
    ]


def test_boundary_probes_do_not_inject_answer_side_mechanisms():
    q = "Чем поиск по собственной документации этого репозитория отличается от поиска по документации внешнего пакета?"
    joined = " ".join(_boundary_texts(q))
    assert all(word not in joined for word in ("manifest", "lockfile", "sync_project_docs", "prefetch"))
    assert len(_boundary_texts(q)) <= 4
