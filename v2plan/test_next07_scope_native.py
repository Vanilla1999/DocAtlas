"""Real service/MCP scope regression. Requires the complete project environment."""
from pathlib import Path

import pytest


@pytest.mark.parametrize('scope,module_path,expected', [
    ('project', None, {'guide.md'}),
    ('all', None, {'guide.md', 'packages/one/guide.md', 'packages/two/guide.md'}),
    ('module', 'packages/one', {'packages/one/guide.md'}),
    ('project', 'packages/one', {'packages/one/guide.md'}),
    ('module', 'packages/missing', set()),
])
def test_native_scope_catalog_roundtrip(tmp_path, scope, module_path, expected):
    import yaml
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.project_context_quality.capture_public_context import capture_public_call
    from eval.evidence_quality_v2.audit import audit_payload
    from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS
    from v2plan.next07_grounded_public import installed

    root = (tmp_path / 'corpus').resolve()
    docs = {path: '# Storage\n\nStorage retention behavior is documented in this guide.\n'
            for path in ('guide.md', 'packages/one/guide.md', 'packages/two/guide.md')}
    write_project(root, docs)
    catalog_path = root / 'docatlas.project-docs.yaml'
    catalog = yaml.safe_load(catalog_path.read_text())
    for entry in catalog['documents']:
        if entry['path'].startswith('packages/'):
            entry.update(scope='module', module_path=str(Path(entry['path']).parent))
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        request = {'project_path': str(root), 'question': 'What is storage retention behavior?', 'scope': scope}
        if module_path:
            request['module_path'] = module_path
        trace = {}
        with installed(service, trace, delivery_limits=COMPACT_READ_LIMITS):
            capture = capture_public_call(service, request)
        assert trace['restored'] and not trace.get('exceptions'), trace.get('exceptions')
        payload = capture['public_payload']
        assert payload.get('status') in {'ok', 'insufficient_evidence'}, payload
        assert {row['path_or_url'] for row in payload.get('sources', [])} == expected
        assert trace.get('handler_validation'), trace
        assert not any(row['errors'] for row in trace['handler_validation'])
        assert not audit_payload(payload, trace['final_snapshot'], root, delivery_limits=COMPACT_READ_LIMITS)
