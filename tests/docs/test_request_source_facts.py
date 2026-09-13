from dataclasses import asdict

from docmancer.docs.domain import source_map
from docmancer.docs.domain.code_graph import build_project_code_graph


def test_map_and_graph_share_parsing_but_keep_independent_selection(tmp_path, monkeypatch):
    (tmp_path / 'client.py').write_text('from worker import dispatch\ndef submit():\n    return dispatch()\n')
    (tmp_path / 'worker.py').write_text('def dispatch():\n    return 1\n')
    map_args = dict(question='client submit', max_files=1, token_budget=900)
    graph_args = dict(question='submit calls dispatch', max_files=8, token_budget=4000)
    expected_map = source_map.build_project_repo_map(tmp_path, **map_args)
    expected_graph = build_project_code_graph(tmp_path, **graph_args)
    assert any(edge.kind == 'imports' for edge in expected_graph.edges)
    observed = []
    original = source_map._map_source_file
    def count(root, path):
        observed.append(path.name)
        return original(root, path)
    monkeypatch.setattr(source_map, '_map_source_file', count)
    facts = source_map.ProjectSourceFacts()
    actual_map = source_map.build_project_repo_map(tmp_path, source_facts=facts, **map_args)
    actual_graph = build_project_code_graph(tmp_path, source_facts=facts, **graph_args)
    assert actual_map == expected_map
    assert asdict(actual_graph) == asdict(expected_graph)
    assert sorted(observed) == ['client.py', 'worker.py']


def test_source_facts_do_not_leak_mutation_or_survive_into_next_request(tmp_path):
    source = tmp_path / 'worker.py'
    source.write_text('def dispatch():\n    return 1\n')
    facts = source_map.ProjectSourceFacts()
    first = source_map.collect_project_source_facts(tmp_path, include_unmatched=True, source_facts=facts)
    first[0]['symbols'].clear()
    again = source_map.collect_project_source_facts(tmp_path, include_unmatched=True, source_facts=facts)
    assert again[0]['symbols']
    source.write_text('def replacement():\n    return 2\n')
    fresh = source_map.collect_project_source_facts(tmp_path, include_unmatched=True,
                                                   source_facts=source_map.ProjectSourceFacts())
    assert fresh[0]['symbols'] != again[0]['symbols']


def test_navigation_requires_relationship_before_graph_expansion():
    from docmancer.docs.domain.retrieval_routing import route_initial_stages, should_run_code_graph
    def runs(question):
        route = route_initial_stages(question=question, mode='auto', dependency_requested=False,
                                     project_doc_items=[])
        return should_run_code_graph(route, question=question,
            source_items=[{'evidence_class': 'absent_in_source'}],
            repo_map_items=[{'path': 'alpha/config.py'}, {'path': 'beta/settings.py'}])[0]
    for question in ('Where is the configuration declared?', 'Какие файлы индексируются?',
                     'Where can I find the settings file?'):
        assert not runs(question), question
    for question in ('Where does the call chain cross modules?',
                     'Где проходит путь от Handler до Storage?',
                     'Where is Handler called by Worker?'):
        assert runs(question), question
