"""Wiring contract tests, not source-guard or native delivery acceptance.

Preparation/packing are spies here. The DTO and the consumer normalizer are real
project definitions. Use next07_grounded_final_run for actual public delivery.
"""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from docmancer.docs.models import ProjectContextResult, ProjectDocsResult
from docmancer.docs.application._unified_context_service_part02 import _UnifiedDocsContextServicePart02
from v2plan import next07_grounded_public as wiring
from v2plan import next07_grounded_final_run as runner


NORMALIZE = _UnifiedDocsContextServicePart02._normalize_project_context


class FakeUnified:
    def __init__(self, service):
        self.service = service
        self.fail_after_context = False
        self.early_return = False

    def get_docs_context(self, question, *, project_path, scope='project', **kwargs):
        if self.early_return:
            return []
        result = self.service.get_project_context(project_path, question, scope=scope, **kwargs)
        if self.fail_after_context:
            raise AttributeError('downstream witness for diagnostic test')
        return NORMALIZE(None, result)


class FakeFacade:
    # Match the production facade's variadic forwarding boundary, not an
    # invented signature that exposes named project_path/question parameters.
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.unified_context = FakeUnified(self)

    def get_project_context(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


@pytest.fixture
def setup(monkeypatch):
    result = ProjectContextResult('/repo', 'question', context_pack=[{'title': 'native'}],
        project_docs=ProjectDocsResult('/repo', 'question'), support_decision=object())
    service = FakeFacade(result)
    rows = [{'project_identity': 'project-A', 'source_class': 'project_doc',
             'doc_scope': 'project', 'path': 'guide.md', 'snippet': 'original bytes'}]
    calls = []

    def prepared(*args, **kwargs):
        calls.append(args)
        return deepcopy(rows)

    monkeypatch.setattr(wiring, 'prepared', prepared)
    return service, result, rows, calls


def test_replace_preserves_type_and_nested_decisions(setup):
    _, original, rows, _ = setup
    result = wiring._replace_context_pack(original, rows)
    assert type(result) is type(original)
    assert result.context_pack == rows
    assert result.project_docs is original.project_docs
    assert result.support_decision is original.support_decision
    assert original.context_pack == [{'title': 'native'}]
    assert NORMALIZE(None, result)[0]['origin_lane'] == 'project'


def test_asdict_is_not_a_project_context_return_value(setup):
    _, original, _, _ = setup
    with pytest.raises(AttributeError, match='context_pack'):
        NORMALIZE(None, asdict(original))


@pytest.mark.parametrize('bad', [{}, ProjectContextResult])
def test_replacement_rejects_untyped_result(bad):
    with pytest.raises(TypeError, match='dataclass'):
        wiring._replace_context_pack(bad, [])


@pytest.mark.parametrize('keywords', [False, True])
def test_installed_retains_dataclass(setup, keywords):
    service, original, rows, calls = setup
    trace = {}
    with wiring.installed(service, trace):
        if keywords:
            result = service.get_project_context(project_path='/repo', question='question', scope='project')
        else:
            result = service.get_project_context('/repo', 'question', scope='project')
        assert NORMALIZE(None, result)[0]['snippet'] == rows[0]['snippet']
        assert isinstance(result, ProjectContextResult)
        assert result.project_docs is original.project_docs
    assert trace['restored'] is True
    assert calls[0][1:3] == ('/repo', 'question')
    assert service.result is original


def test_real_normalizer_accepts_repaired_value(setup):
    service, _, rows, _ = setup
    trace = {}
    with wiring.installed(service, trace):
        result = service.unified_context.get_docs_context('question', project_path='/repo')
        assert result[0]['snippet'] == rows[0]['snippet']
    assert trace['restored'] is True
    assert not trace.get('exceptions')


def test_projection_uses_post_guard_rows_not_cached_rows(setup, monkeypatch):
    service, _, _, _ = setup
    packed = []
    monkeypatch.setattr(wiring, 'first_fit', lambda rows, *args: (packed.append(deepcopy(rows)), {}))
    trace = {}
    with wiring.installed(service, trace):
        rows = service.unified_context.get_docs_context('question', project_path='/repo')
        guarded = deepcopy(rows)
        guarded[0]['instruction_risk_flags'] = ['blocked-by-native-annotation']
        wiring.context_tools.project_docs_context(retrieval={'context_pack': guarded})
        wiring.context_tools.project_docs_context(retrieval={'context_pack': []})
    assert packed[0][0]['instruction_risk_flags'] == ['blocked-by-native-annotation']
    assert packed[1] == []  # A native removal cannot be undone by a cached list.


def test_downstream_exception_is_captured_before_dispatcher_sanitizes(setup):
    service, _, _, _ = setup
    service.unified_context.fail_after_context = True
    trace = {}
    with pytest.raises(AttributeError, match='downstream witness'):
        with wiring.installed(service, trace):
            service.unified_context.get_docs_context('question', project_path='/repo')
    error = trace['exceptions'][-1]
    assert error['stage'] == 'unified_context'
    assert error['exception_type'] == 'AttributeError'
    assert 'Traceback' in error['traceback']
    assert 'downstream witness' in error['traceback']
    assert trace['restored'] is True


def test_hooks_restored_when_context_body_raises(setup):
    service, _, _, _ = setup
    before = (service.get_project_context, service.unified_context.get_docs_context,
        wiring.context_tools.project_docs_context, wiring.context_tools.validate_model_visible_projection)
    trace = {}
    with pytest.raises(RuntimeError, match='outer'):
        with wiring.installed(service, trace):
            raise RuntimeError('outer')
    after = (service.get_project_context, service.unified_context.get_docs_context,
        wiring.context_tools.project_docs_context, wiring.context_tools.validate_model_visible_projection)
    assert before == after
    assert trace['restored'] is True


def test_handler_validator_result_is_not_modified(setup, monkeypatch):
    service, _, _, _ = setup
    errors = ['source-damage']
    calls = []
    def validator(*args, **kwargs):
        calls.append((args, kwargs))
        return errors
    monkeypatch.setattr(wiring.context_tools, 'validate_model_visible_projection', validator)
    trace = {}
    with wiring.installed(service, trace):
        result = wiring.context_tools.validate_model_visible_projection({'kind': 'docs_context'},
            snapshot={'id': {}}, max_tokens=800)
        assert result is errors
    assert calls[0][1] == {'snapshot': {'id': {}}, 'max_tokens': 800}
    assert trace['handler_validation'] == [{'errors': errors, 'max_tokens': 800}]


def test_next_request_cannot_reuse_previous_identity(setup):
    service, _, _, _ = setup
    trace = {}
    with wiring.installed(service, trace):
        service.unified_context.get_docs_context('first', project_path='/repo')
        service.unified_context.early_return = True
        service.unified_context.get_docs_context('second', project_path='/repo')
        with pytest.raises(RuntimeError, match='not reached'):
            wiring.context_tools.project_docs_context(retrieval={'context_pack': []})
    assert trace['exceptions'][-1]['stage'] == 'projection'


@pytest.mark.parametrize('arguments', [
    {'scope': 'invalid'}, {'scope': 'project', 'module': 'legacy-name'},
    {'scope': 'project', 'mode': 'deps-only'},
    {'scope': 'project', 'library': 'external-library'},
    {'scope': 'project', 'lookup_queries': ('another request',)},
    {'scope': 'project', 'lifecycle_intent': 'historical'},
    {'scope': 'project', 'request_intent': 'change'},
])
def test_unsupported_scope_does_not_silently_run_project_preparation(setup, arguments):
    service, _, _, calls = setup
    trace = {}
    with wiring.installed(service, trace):
        with pytest.raises(NotImplementedError, match='project-document'):
            service.get_project_context('/repo', 'question', **arguments)
    assert not calls
    assert not service.calls
    assert trace['restored'] is True


def good_capture(monkeypatch):
    docs = {
        'default.md': '# LeaseClient\n\nThe default timeout is 17 seconds.\n',
        'error.md': '# LeaseClient\n\nAn expired operation raises `LeaseExpired`.\n',
    }
    payload = dict(kind='docs_context', sources=[{'path_or_url': k, 'snippet': v} for k, v in docs.items()],
        answer_supported=False, answer_available=False, edit_ready=False, support_status='retrieval_only')
    trace = dict(projection_calls=1, validator=[], handler_validation=[{'errors': [], 'max_tokens': 800}],
        budget=100, restored=True)
    # This suite tests the runner's decision boundary, not token estimation.
    monkeypatch.setattr(runner, 'docs_context_budget_tokens', lambda payload: 700)
    return {'public_payload': payload}, trace, docs


def test_runner_checks_final_public_result(monkeypatch):
    capture, trace, docs = good_capture(monkeypatch)
    result = runner._assess_capture(capture, trace, docs, 17, 'LeaseExpired')
    assert result['passed'] and result['cost'] == 700 and result['pre_handler_cost'] == 100


@pytest.mark.parametrize('failure', ['final_budget', 'credit', 'validator', 'not_validated', 'condition'])
def test_runner_cannot_promote_intermediate_success(monkeypatch, failure):
    capture, trace, docs = good_capture(monkeypatch)
    if failure == 'final_budget':
        monkeypatch.setattr(runner, 'docs_context_budget_tokens', lambda payload: 801)
    elif failure == 'credit':
        capture['public_payload']['answer_supported'] = True
    elif failure == 'validator':
        trace['handler_validation'][0]['errors'] = ['late mutation']
    elif failure == 'not_validated':
        trace['handler_validation'] = []
    else:
        capture['public_payload']['sources'][1]['snippet'] = '# LeaseClient\nLeaseExpired'
    result = runner._assess_capture(capture, trace, docs, 17, 'LeaseExpired')
    assert result['valid'] and not result['passed']


def test_runner_distinguishes_meaningful_empty_from_exception(monkeypatch):
    capture, trace, docs = good_capture(monkeypatch)
    capture['public_payload'] = {'status': 'insufficient_evidence', 'sources': []}
    result = runner._assess_capture(capture, trace, docs, 17, 'LeaseExpired')
    assert result['valid'] and not result['passed']
    trace['exceptions'] = [{'exception_type': 'AttributeError'}]
    result = runner._assess_capture(capture, trace, docs, 17, 'LeaseExpired')
    assert not result['valid'] and not result['passed']
