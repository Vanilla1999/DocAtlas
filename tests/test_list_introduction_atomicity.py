"""Source-local list relations survive chunk packing and explicit index refresh."""
from __future__ import annotations

import pytest

from docmancer.core import structured_chunking as chunking
from docmancer.docs.domain.project_state import partition_project_doc_state


@pytest.mark.parametrize('identity', [
    'guide.md',
    'project_file:git:example/Aurora:docs/product.md',
    'project_file:git:example/deeply/nested/Aurora:docs/product.md',
])
def test_list_introduction_and_items_form_one_contiguous_atom(identity):
    intro = 'Aurora does **not** replace:\n\n'
    items = '- a scheduler;\n- an archive;\n- an audit service;\n- an operator;\n- a catalog;\n- a message broker.\n\n'
    source = '# Boundaries\n\n' + 'Background ownership responsibility. ' * 10 + '\n\n' + intro + items + 'Independent ending.\n'
    atoms = chunking._atom_spans(source, 0, len(source))
    assert any(source[a.start:a.end] == intro + items for a in atoms)
    _, children = chunking.chunk_markdown_parent_child(source, identity, chunking.ChunkingConfig(target_tokens=80, hard_max_tokens=200))
    assert any(intro + items in c.display_text for c in children)
    assert ''.join(c.display_text for c in children) == source
    assert all(chunking.estimate_utf8_tokens(c.retrieval_text) <= 200 for c in children)
    assert all(source.encode()[c.byte_start:c.byte_end].decode() == c.display_text for c in children)

    # Exercise final model-visible projection, not only the chunk/window helper.
    # Generic responsibilities precede the separate non-replacement relation.
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

    path = identity.rsplit(":", 1)[-1]
    project_identity = (
        identity.removeprefix("project_file:").rsplit(":", 1)[0]
        if identity.startswith("project_file:") else "path:/test/Aurora"
    )
    retrieval = {
        "context_pack": [{
            "source_class": "project_doc", "path": path,
            "heading_path": "Boundaries", "content": child.display_text,
            "stable_chunk_id": child.stable_id,
            "char_start": child.char_start, "char_end": child.char_end,
            "line_start": child.line_start, "line_end": child.line_end,
            "project_identity": project_identity, "authority": "source_of_truth",
            "doc_scope": "project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized",
            "risk_flags": [], "retrieval_query_ids": ["query-original"],
            "retrieval_query_matches": {
                "query-original": {"qualified": True, "mode": "and"},
            },
        } for child in children],
        "documentation_query_plan": {
            "query_ids": ["query-original"],
            "queries": [{
                "query_id": "query-original", "origin": "original",
                "text": "What does Aurora not replace?",
            }],
        },
    }
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert payload["status"] == "ok"
    assert payload["kind"] == "docs_context"
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert 0 < len(payload["sources"]) <= 3
    assert payload["estimated_tokens"] <= 800
    assert any((intro + items).strip() in row["snippet"] for row in payload["sources"])
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    lines = source.splitlines(keepends=True)
    for row in payload["sources"]:
        assert row["project_identity"] == project_identity
        assert row["path_or_url"] == path
        assert row["snippet"] in "".join(lines[row["line_start"] - 1:row["line_end"]])


@pytest.mark.parametrize('prefix', ['Unrelated ending.\n\n', '# Heading:\n\n', '```text\nExample:\n```\n\n', '- Previous list:\n\n'])
def test_only_adjacent_prose_introduction_can_bind_a_list(prefix):
    source = prefix + '- first item\n- second item\n'
    atoms = chunking._atom_spans(source, 0, len(source))
    assert not any(a.start == 0 and a.end == len(source) for a in atoms)


def test_oversized_introduced_list_still_respects_hard_limit_and_source_spans():
    source = '# Rules\n\nAurora requires:\n\n' + ''.join(f'- правило {i}: сохранение исходного текста.\n' for i in range(80))
    _, children = chunking.chunk_markdown_parent_child(source, 'rules.md', chunking.ChunkingConfig(target_tokens=32, hard_max_tokens=80))
    assert ''.join(c.display_text for c in children) == source
    assert all(chunking.estimate_utf8_tokens(c.retrieval_text) <= 80 for c in children)
    assert all(left.char_end == right.char_start for left, right in zip(children, children[1:]))


def test_atomization_revision_changes_configuration_fingerprint(monkeypatch):
    current = chunking.ChunkingConfig().config_hash
    monkeypatch.setattr(chunking, '_ATOMIZATION_REVISION', 'previous-parser', raising=False)
    assert chunking.ChunkingConfig().config_hash != current


def test_parser_configuration_drift_is_stale_not_a_source_edit():
    candidate = {'path': 'README.md', 'content_hash': 'same', 'catalog_entry_hash': 'same', 'mtime_ns': 1}
    current, stale, ignored = partition_project_doc_state([candidate], [{**candidate, 'chunking_current': False}])
    assert not current and not ignored
    assert stale[0]['stale_reasons'] == ['chunking_configuration_changed']
    assert stale[0]['current_content_hash'] == 'same'


def test_old_generation_requires_explicit_sync_without_touching_project_files(tmp_path, monkeypatch):
    from tests.docs.test_question_frame_paraphrase_e2e import _service
    from docmancer.mcp.docs_server import call_docs_tool_payload

    project = tmp_path / 'project'
    project.mkdir()
    path = project / 'README.md'
    path.write_text('# Aurora\n\nAurora does not replace:\n\n- a scheduler;\n- an archive.\n')
    before = path.read_bytes()
    service = _service(tmp_path, monkeypatch)
    with monkeypatch.context() as previous:
        previous.setattr(chunking, '_ATOMIZATION_REVISION', 'previous-parser', raising=False)
        assert service.sync_project_docs(str(project), with_vectors=False).status == 'success'
        old_generation = service._agent_instance().store.active_generation_id()
    payload = call_docs_tool_payload('get_docs_context', {'question': 'What does Aurora not replace?', 'project_path': str(project), 'scope': 'all'}, service)
    assert service._agent_instance().store.active_generation_id() == old_generation
    assert path.read_bytes() == before
    action = payload.get('recommended_next_action') or {}
    assert payload['status'] == 'insufficient_evidence'
    assert action.get('tool') == 'prepare_docs'
    assert action.get('arguments_patch', {}).get('action') == 'sync_project_docs'
    assert action.get('auto_execute') is False
    assert service.sync_project_docs(str(project), with_vectors=False).status == 'success'
    assert service._agent_instance().store.active_generation_id() != old_generation
    assert path.read_bytes() == before


def test_parser_revision_does_not_churn_unchanged_evidence_identities(monkeypatch):
    source = '# Aurora\n\nAn independently versioned unchanged source fact.\n'
    with monkeypatch.context() as previous:
        previous.setattr(chunking, '_ATOMIZATION_REVISION', 'previous-parser')
        old_config = chunking.ChunkingConfig()
        old_fingerprint = old_config.config_hash
        _, old_children = chunking.chunk_markdown_parent_child(source, 'guide.md', old_config)
    _, current = chunking.chunk_markdown_parent_child(source, 'guide.md')
    assert chunking.ChunkingConfig().config_hash != old_fingerprint
    assert [c.stable_id for c in current] == [c.stable_id for c in old_children]
    assert [c.sqlite_id for c in current] == [c.sqlite_id for c in old_children]
    assert [c.vector_id for c in current] == [c.vector_id for c in old_children]
    assert [c.display_text for c in current] == [c.display_text for c in old_children]
    assert current[0].config_hash != old_children[0].config_hash


def test_unchanged_evidence_retains_pre_revision_identity_contract():
    import hashlib
    source = '# Aurora\n\nAn independently versioned unchanged source fact.\n'
    config = chunking.ChunkingConfig()
    parents, children = chunking.chunk_markdown_parent_child(source, 'guide.md', config)
    legacy_identity_config = chunking._digest(
        config.schema_version, config.estimator_version,
        str(config.target_tokens), str(config.hard_max_tokens), str(config.overlap_tokens),
    )
    assert len(children) == 1
    expected = 'child-' + chunking._digest(
        parents[0].logical_id, legacy_identity_config,
        hashlib.sha256(source.encode()).hexdigest(), '1',
    )[:40]
    assert children[0].stable_id == expected
