"""Real service/MCP scope regression. Requires the complete project environment."""
from pathlib import Path

import pytest


@pytest.mark.parametrize('scope,module_path,question,required,allowed', [
    ('project', None, 'What is ProjectStorage retention alpha?',
     {'guide.md'}, {'guide.md'}),
    ('all', None, 'What is ModuleOne retention beta?',
     {'packages/one/guide.md'}, {'guide.md', 'packages/one/guide.md', 'packages/two/guide.md'}),
    ('module', 'packages/one', 'What is ModuleOne retention beta?',
     {'packages/one/guide.md'}, {'packages/one/guide.md'}),
    ('project', 'packages/one', 'What is ModuleOne retention beta?',
     {'packages/one/guide.md'}, {'packages/one/guide.md'}),
    ('module', 'packages/missing', 'What is ModuleOne retention beta?',
     set(), set()),
])
def test_native_scope_catalog_roundtrip(tmp_path, scope, module_path, question, required, allowed):
    import yaml
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.project_context_quality.capture_public_context import capture_public_call
    from eval.evidence_quality_v2.audit import audit_payload
    from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS
    from v2plan.next07_grounded_public import installed

    root = (tmp_path / 'corpus').resolve()
    docs = {
        'guide.md': '# ProjectStorage\n\nProjectStorage retention alpha is documented in this guide.\n',
        'packages/one/guide.md': '# ModuleOne\n\nModuleOne retention beta is documented in this guide.\n',
        'packages/two/guide.md': '# ModuleTwo\n\nModuleTwo retention gamma is documented in this guide.\n',
    }
    write_project(root, docs)
    catalog_path = root / 'docatlas.project-docs.yaml'
    catalog = yaml.safe_load(catalog_path.read_text())
    for entry in catalog['documents']:
        if entry['path'].startswith('packages/'):
            entry.update(scope='module', module_path=str(Path(entry['path']).parent))
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        request = {'project_path': str(root), 'question': question, 'scope': scope}
        if module_path:
            request['module_path'] = module_path
        trace = {}
        with installed(service, trace, delivery_limits=COMPACT_READ_LIMITS):
            capture = capture_public_call(service, request)
        assert trace['restored'] and not trace.get('exceptions'), trace.get('exceptions')
        payload = capture['public_payload']
        assert payload.get('status') in {'ok', 'insufficient_evidence'}, payload
        visible = {row['path_or_url'] for row in payload.get('sources', [])}
        assert required.issubset(visible)
        assert visible.issubset(allowed)
        assert trace.get('handler_validation'), trace
        assert not any(row['errors'] for row in trace['handler_validation'])
        assert not audit_payload(payload, trace['final_snapshot'], root, delivery_limits=COMPACT_READ_LIMITS)
