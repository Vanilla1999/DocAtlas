import json
import hashlib

import pytest

from tests.docs.test_retrieval_ablation_packet import project_store
from experiments.retrieval_ablation.adapters import native_diagnostic
from experiments.retrieval_ablation.saved_pool import replay_pool, save_pool


def test_saved_pool_reproduces_b_and_assembles_without_search(tmp_path, monkeypatch):
    from docmancer.core.sqlite_store import SQLiteStore
    text = '# API\n\n' + ('target contract ' * 45) + '\n\n' + ('condition detail ' * 45) + '\n'
    store, sources, filters = project_store(tmp_path, {'docs/api.md': text})
    result = native_diagnostic(store, ['target contract'], filters=filters, sources=sources)
    bundle = tmp_path / 'saved'
    save_pool(store, result, sources, ['target contract'], bundle)
    before = (bundle / 'snapshot.db').read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError('replay must not retrieve')
    monkeypatch.setattr(SQLiteStore, '_search_rows', forbidden)
    replay = replay_pool(bundle)
    assert replay['new_search_count'] == 0
    assert replay['B']['model_visible_packet'] == result['model_visible_packet']
    assert replay['D_L']['packet_audit_errors'] == []
    assert replay['D_L']['packet_budget_tokens'] <= 800
    assert any(d['expanded'] for d in replay['D_L']['assembly_decisions'])
    assert replay_pool(bundle)['D_L']['model_visible_packet'] == replay['D_L']['model_visible_packet']
    assert (bundle / 'snapshot.db').read_bytes() == before


def test_saved_pool_fails_closed_on_changed_artifacts(tmp_path):
    store, sources, filters = project_store(tmp_path)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    bundle = tmp_path / 'saved'
    save_pool(store, result, sources, ['retry budget'], bundle)
    payload = json.loads((bundle / 'pool.json').read_text())
    payload['result']['candidates'][0]['row']['display_text'] = 'forged'
    (bundle / 'pool.json').write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='hash mismatch'):
        replay_pool(bundle)
    # Recomputed unsigned hashes do not grant evidence authority.
    manifest = json.loads((bundle / 'manifest.json').read_text())
    manifest['pool.json'] = hashlib.sha256((bundle / 'pool.json').read_bytes()).hexdigest()
    (bundle / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        replay_pool(bundle)


def test_saved_pool_retains_oversized_and_owner_boundary_controls(tmp_path):
    docs = {'docs/api.md': '# API\n\n' + ('target contract with condition ' * 90)
            + '\n\n## Other\n\n' + ('foreign target contract ' * 35) + '\n'}
    store, sources, filters = project_store(tmp_path, docs)
    result = native_diagnostic(store, ['target contract'], filters=filters, sources=sources)
    bundle = tmp_path / 'saved'
    save_pool(store, result, sources, ['target contract'], bundle)
    replay = replay_pool(bundle)
    assert replay['D_L']['packet_budget_tokens'] <= 800
    for decision in replay['D_L']['assembly_decisions']:
        assert decision['parent_char_start'] <= decision['assembled_char_start']
        assert decision['assembled_char_end'] <= decision['parent_char_end']
    assert replay['B']['packet_omissions']
