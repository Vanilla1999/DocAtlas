"""Live read tails retain literal context and explicit technical boundaries."""
import builtins
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from docmancer.docs.application import context_candidate_ranking as ranking
from docmancer.docs.application import recovery
from docmancer.docs.domain import need_composition, source_map
from docmancer.docs.domain.source_boundary import SourceBoundary


def _declare_code_files(root, *paths):
    (root / "docatlas.project-docs.yaml").write_text(
        json.dumps({"schema_version": 1, "documents": [], "code_files": list(paths)}),
        encoding="utf-8",
    )


@pytest.mark.parametrize('question', [
    'What is Alpha? How is Beta configured?',
    'Что такое Alpha? Как настроить Beta?',
])
def test_ranking_never_calls_nl_independence_and_preserves_tuple_slots(monkeypatch, question):
    def forbidden(*args, **kwargs):
        raise AssertionError('NL independence parser executed')

    monkeypatch.setattr(need_composition, 'independent_sentence_spans', forbidden)
    monkeypatch.setattr(ranking, 'attributable_query_ids', lambda rows: {'need-1'})
    monkeypatch.setattr(ranking, '_fully_matched_query_ids', lambda rows: set())
    keys = []

    def capture(values, *, key, reverse):
        rows = list(values)
        keys.extend(key(row) for row in rows)
        return builtins.sorted(rows, key=key, reverse=reverse)

    monkeypatch.setattr(ranking, 'sorted', capture, raising=False)
    candidates = [{'path': 'Guide.md', 'snippet': 'Alpha Beta', 'retrieval_query_matches': {
        'need-1': {'qualified': True, 'match_ratio': 0.9,
                   'query_text': question.split('?')[0] + '?'},
    }}]
    assert ranking._facet_aware_candidates(
        candidates, query_text={'query-original': question}, required_query_ids=set(),
        need_query_ids={'need-1'},
    ) == candidates
    assert len(keys[0]) == 32
    assert keys[0][0:6] == (1, 0.0, 0, 0.0, (0.0,) * 9, 0)
    assert len(keys[0][31]) == 10


@pytest.mark.parametrize('question', [
    'implement src/client.py so it does not remove Alpha',
    'удали src/client.py только если Alpha отключён',
    'According to Guide.md, what does it say about Alpha?',
    'What does the project documentation say about Alpha?',
    '  src/client.py for Alpha\nthen preserve Beta  ',
    'Alpha ' * 100,
])
@pytest.mark.parametrize('origin', ['retrieval', 'selection'])
def test_recovery_keeps_original_fragment_without_question_synthesis(monkeypatch, question, origin):
    monkeypatch.setattr(recovery, 'diagnose_proofability', lambda selection: {
        'origin': origin, 'reason_codes': ['no_candidates'],
    })
    selection = SimpleNamespace(support_decision=SimpleNamespace(answer_supported=False))
    diagnosis = recovery.build_recovery_diagnosis(question, selection)
    assert diagnosis['disposition'] == 'search_local_source'
    assert diagnosis['problem_spans'] == [question.strip()]
    assert 'suggested_questions' not in diagnosis
    assert recovery._suggested_questions(question, (), evidence_path='Guide.md') == []
    assert 'rephrase_exhausted' not in diagnosis
    assert diagnosis['documentation_supported'] is False
    assert diagnosis['hard_stop'] is False
    action = recovery.recovery_action(diagnosis, project_path='/project', scope='module')
    assert action['type'] == 'search_local_source'
    assert action['auto_execute'] is action['repeat_docs_context'] is False
    assert 'arguments_patch' not in action and 'decision_options' not in action
    assert action['query_terms'] == [question.strip()]


def test_legacy_supplied_rephrase_cannot_emit_retry_or_equivalence():
    assert recovery.recovery_action({
        'disposition': 'rephrase_question',
        'suggested_questions': ['What does Alpha mean?', 'same original question'],
    }) is None


@pytest.mark.parametrize('reason', sorted(recovery._OPERATIONAL_RECOVERY_REASONS))
def test_recovery_preserves_operational_states(monkeypatch, reason):
    monkeypatch.setattr(recovery, 'diagnose_proofability', lambda selection: {})
    diagnosis = recovery.build_recovery_diagnosis(
        'remove src/alpha.py', SimpleNamespace(), operational_reason_code=reason,
    )
    assert diagnosis['disposition'] == 'use_operational_recovery'
    assert diagnosis['reason_code'] == reason
    assert diagnosis['documentation_supported'] is False
    assert recovery.recovery_action(diagnosis) is None


def test_recovery_keeps_conflict_hard_stop_and_supported_early_return(monkeypatch):
    monkeypatch.setattr(recovery, 'diagnose_proofability', lambda selection: {
        'origin': 'source_documentation',
        'reason_codes': ['conflicting_authoritative_evidence'],
    })
    diagnosis = recovery.build_recovery_diagnosis('Alpha', SimpleNamespace())
    assert diagnosis['hard_stop'] is True
    assert diagnosis['disposition'] == 'resolve_authoritative_conflict'
    assert recovery.recovery_action(diagnosis) is None
    supported = SimpleNamespace(support_decision=SimpleNamespace(answer_supported=True))
    assert recovery.build_recovery_diagnosis('Alpha', supported) == {}


def test_projection_recovery_keeps_bounded_nonautomatic_local_inspection(monkeypatch):
    monkeypatch.setattr(recovery, 'diagnose_proofability', lambda selection: {})
    question = 'implement src/alpha.py for Alpha'
    action = recovery.projection_recovery_action(
        question, None, projection={'context_available': False},
        retrieval={'context_pack': []}, request={'project_path': '/project'},
    )
    assert action['query_terms'] == [question]
    assert action['auto_execute'] is action['repeat_docs_context'] is False
    assert recovery.projection_recovery_action(
        question, None, projection={'context_available': True}, retrieval={}, request={},
    ) is None


@pytest.mark.parametrize('question', [
    'generated code Alpha', 'generated artifact Alpha', 'generated source Alpha',
    'сгенерированн файл Alpha', 'сгенерированный код Alpha',
    'alpha.g.dart Alpha', 'alpha.freezed.dart Alpha', 'alpha.pb.go Alpha',
])
@pytest.mark.parametrize('include_generated', [None, False, True])
def test_only_explicit_generated_opt_in_authorizes_source_scanning(tmp_path, question, include_generated, monkeypatch):
    (tmp_path / 'normal.py').write_text('Alpha = "literal"\n')
    (tmp_path / 'alpha.g.dart').write_text('class Alpha {}\n')
    (tmp_path / 'alpha.freezed.dart').write_text('class Alpha {}\n')
    (tmp_path / 'alpha.pb.go').write_text('type Alpha struct {}\n')
    kwargs = {'include_generated': include_generated}
    mixed_members = ('normal.py', 'alpha.g.dart', 'alpha.freezed.dart', 'alpha.pb.go')
    source_bytes = {path: (tmp_path / path).read_bytes() for path in mixed_members}
    original_read_text = Path.read_text
    observed = {}

    def observe_read(path, *args, **options):
        value = original_read_text(path, *args, **options)
        if path.is_relative_to(tmp_path) and path.suffix in {'.py', '.dart', '.go'}:
            observed.setdefault(path.relative_to(tmp_path).as_posix(), []).append(
                hashlib.sha256(value.encode('utf-8')).hexdigest()
            )
        return value

    monkeypatch.setattr(Path, 'read_text', observe_read)
    # Membership is never derived from the question, flag, or returned rows.
    # Each authored declaration is exercised with the same original arguments.
    for members in (mixed_members, ('normal.py',)):
        _declare_code_files(tmp_path, *members)
        observed.clear()
        facts = source_map.collect_project_source_facts(tmp_path, question=question, **kwargs)
        repo = source_map.build_project_repo_map(tmp_path, question=question, **kwargs)
        evidence = source_map.build_project_source_evidence(
            tmp_path, question=question,
            requirements=['normal.py', 'alpha.g.dart', 'alpha.freezed.dart', 'alpha.pb.go'],
            **kwargs,
        )
        if members == mixed_members and include_generated is not True:
            assert (facts, repo, evidence) == ([], [], [])
            assert observed == {}
        else:
            for rows in (facts, repo, evidence):
                assert {row['path'] for row in rows if row.get('path')} == set(members)
            assert observed == {
                path: [hashlib.sha256(source_bytes[path]).hexdigest()] * 3 for path in members
            }


def test_query_words_remain_literal_without_nl_stopwords():
    words = 'and are for from how the this that where with как где для или что это этой'
    assert source_map._query_terms(words) == words.split()
    assert source_map._query_terms('`как` "this" Alpha') == ['как', 'this', 'Alpha']
    assert len(source_map._query_terms(' '.join(f'word{i}' for i in range(40)))) == 24


def test_source_map_omits_semantic_status_summary_but_keeps_structural_facts(tmp_path):
    (tmp_path / 'client.py').write_text(
        'import os\nclass Client:\n    def send(self):\n        return "готово"\n'
        'state = "active"\n# pending done failed unknown\n', encoding='utf-8',
    )
    _declare_code_files(tmp_path, 'client.py')
    (fact,) = source_map.collect_project_source_facts(tmp_path, include_unmatched=True)
    assert fact['language'] == 'python' and fact['imports'] == ['os']
    assert [(symbol['name'], symbol['line_start']) for symbol in fact['symbols']] == [
        ('Client', 2), ('send', 3),
    ]
    assert fact['string_literals'] == ['готово', 'active']
    assert fact['status_like_tokens'] == []
    assert 'status_like_tokens:' not in fact['content']
    assert 'pending' not in fact['content']
    assert fact['line_start'] == 1 and fact['line_end'] == 6
    assert fact['token_estimate'] == max(1, len(fact['content']) // 4)


def test_explicit_generated_opt_in_preserves_source_boundary_and_scan_limits(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'outside').mkdir()
    (tmp_path / 'src' / 'allowed.g.dart').write_text('class Alpha {}\n')
    (tmp_path / 'src' / 'blocked.g.dart').write_text('class Alpha {}\n')
    (tmp_path / 'src' / 'large.g.dart').write_text('Alpha ' * 100)
    (tmp_path / 'outside' / 'escape.py').write_text('Alpha = 1\n')
    (tmp_path / 'src' / 'link.py').symlink_to(tmp_path / 'outside' / 'escape.py')
    boundary = SourceBoundary(
        source_roots=('src',), exclude_paths=('src/blocked.g.dart',),
        max_file_bytes=100, max_scanned_files=10, max_scanned_bytes=1000,
        code_files=('src/allowed.g.dart',),
    )
    facts = source_map.collect_project_source_facts(
        tmp_path, question='Alpha', include_generated=True, source_boundary=boundary,
    )
    assert [fact['path'] for fact in facts] == ['src/allowed.g.dart']
    assert source_map.collect_project_source_facts(
        tmp_path, include_unmatched=True, include_generated=True,
        source_boundary=SourceBoundary(enabled=False),
    ) == []
    assert source_map.collect_project_source_facts(tmp_path, max_files=0) == []
    assert source_map.collect_project_source_facts(tmp_path, token_budget=0) == []
    for denied in ('src/blocked.g.dart', 'src/large.g.dart', 'outside/escape.py', 'src/link.py'):
        assert source_map.collect_project_source_facts(
            tmp_path, question='Alpha', include_generated=True,
            source_boundary=replace(boundary, code_files=('src/allowed.g.dart', denied)),
        ) == []
    assert source_map.collect_project_source_facts(
        tmp_path, include_unmatched=True, include_generated=True,
        source_boundary=replace(boundary, enabled=False),
    ) == []
    for budget in ({'max_files': 0}, {'token_budget': 0}):
        assert source_map.collect_project_source_facts(
            tmp_path, include_unmatched=True, include_generated=True,
            source_boundary=boundary, **budget,
        ) == []


def test_source_snippet_scrubbing_and_bounded_output_survive(tmp_path):
    (tmp_path / 'settings.py').write_text('password = "private-value"\nAlpha = 1\n')
    _declare_code_files(tmp_path, 'settings.py')
    (evidence,) = source_map.build_project_source_evidence(
        tmp_path, requirements=['password'], max_items=1,
    )
    assert 'private-value' not in evidence['content']
    assert '[REDACTED]' in evidence['snippet']
    assert evidence['line_start'] == evidence['line_end'] == 1
    assert evidence['path'] == 'settings.py'
    assert len(source_map.build_project_source_evidence(
        tmp_path, requirements=['password', 'Alpha'], max_items=1,
    )) <= 1


def test_programming_grammar_does_not_create_keyword_symbols():
    symbols = source_map._extract_generic_symbols('class Alpha {}\nif (ready) {}\n')
    assert [symbol['name'] for symbol in symbols] == ['Alpha']
    assert 'if' in source_map._KEYWORDS and 'class' in source_map._KEYWORDS
    assert source_map.SOURCE_FILE_LANGUAGES['.dart'] == 'dart'
