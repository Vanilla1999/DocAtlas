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

