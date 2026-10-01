import pytest
import json
import hashlib

from experiments.retrieval_ablation.source_artifact import canonicalize, save_artifact, load_artifact, bind_packet_provenance
from experiments.retrieval_ablation.structure import commonmark_parents


def test_html_conversion_preserves_separate_original_and_canonical_provenance(tmp_path):
    raw = (b'<html><body><main><h2>Client.alpha()</h2>'
           b'<p>This method raises ErrAlpha on cancellation only when enabled. '
           b'See Client.beta().</p><pre><code>pattern = " /-S"\nstar = "*"\n'
           b'double_star = "**"</code></pre><h2>Client.beta()</h2>'
           b'<p>This method returns normally on shutdown.</p></main></body></html>')
    artifact = canonicalize(raw, source_format='html')
    root = tmp_path / 'artifact'
    save_artifact(artifact, root)
    assert load_artifact(root) == artifact
    assert artifact.original == raw
    assert artifact.original != artifact.canonical
    text = artifact.canonical.decode()
    assert ' /-S' in text and 'double_star' in text
    parents = commonmark_parents(text, 'derived-source')
    assert [p.title for p in parents] == ['Client.alpha()', 'Client.beta()']
    assert 'returns normally' not in parents[0].display_text
    quote = artifact.quote(parents[0].char_start, parents[0].char_end)
    assert quote['text'] == parents[0].display_text
    assert quote['provenance']['evidence_coordinate_space'] == 'canonical_utf8_markdown'
    assert quote['provenance']['original_coordinate_mapping'] == 'NOT_PROVIDED'
    from tests.docs.test_retrieval_ablation_packet import project_store
    from experiments.retrieval_ablation.adapters import native_diagnostic
    store, sources, filters = project_store(tmp_path, {'docs/canonical.md': text})
    result = native_diagnostic(store, ['ErrAlpha cancellation'], filters=filters, sources=sources)
    assert result['model_visible_packet']['sources']
    locators = bind_packet_provenance(result, {'docs/canonical.md': artifact})
    assert len(locators) == len(result['model_visible_packet']['sources'])
    assert all(row['provenance']['original_coordinate_mapping'] == 'NOT_PROVIDED'
               for row in locators.values())
    with pytest.raises(ValueError, match='canonical hash mismatch'):
        bind_packet_provenance(result, {'docs/canonical.md': canonicalize(b'# Other\n\nbody', source_format='markdown')})
    with pytest.raises(ValueError, match='missing source artifact'):
        bind_packet_provenance(result, {})
    (root / 'original.bin').write_bytes(b'changed')
    with pytest.raises(ValueError, match='provenance mismatch'):
        load_artifact(root)
    (root / 'original.bin').write_bytes(raw)
    (root / 'canonical.md').write_bytes(b'# Forged owner\n\nforged contract')
    provenance = artifact.provenance()
    provenance['canonical_sha256'] = hashlib.sha256((root / 'canonical.md').read_bytes()).hexdigest()
    (root / 'provenance.json').write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match='conversion did not reproduce'):
        load_artifact(root)


def test_native_markdown_and_unsupported_format_fail_closed(tmp_path):
    raw = '## Méthode\r\n\r\nDo not retry cancellation.\r\n'.encode()
    artifact = canonicalize(raw, source_format='markdown')
    assert artifact.original == artifact.canonical == raw
    with pytest.raises(ValueError, match='unsupported'):
        canonicalize(b'API\n~~~\n\ncontract', source_format='rst')
    for start, end in [(-1, 3), (0, 10000), (True, 2), (2, 2)]:
        with pytest.raises(ValueError):
            artifact.quote(start, end)
