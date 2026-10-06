from types import SimpleNamespace

from docmancer.docs.domain.answer_completeness import (
    derive_project_answer_completeness,
    evaluate_project_answer_completeness,
    extract_project_answer_requirements,
    extract_query_relevance_terms,
)
from docmancer.docs.domain.quality import internal_noise_score, looks_like_code_or_command


def test_free_text_does_not_generate_story_or_architecture_requirements():
    assert extract_project_answer_requirements("Create a chat UI Cubit Service API") == []
    assert extract_project_answer_requirements("Добавь заявку и экран чата") == []


def test_literal_relevance_terms_have_no_synonyms_and_keep_existing_cap():
    assert extract_query_relevance_terms("cleanup indexing browser") == ["cleanup", "indexing", "browser"]
    assert len(extract_query_relevance_terms(" ".join(f"word{i}" for i in range(20)))) == 8


def test_authoritative_context_and_overlap_do_not_authorize_answer_or_edit():
    result = evaluate_project_answer_completeness(
        question="Explain ChatService", context_pack=[{
            "source_class": "project_doc", "authority": "source_of_truth", "content": "ChatService",
        }], answer_available=True, intent=SimpleNamespace(wants_how_to=True),
    )
    assert result["answer_type"] == "partial"
    assert result["answer_completeness"]["coverage_score"] == 0.0
    assert result["answer_completeness"]["edit_ready"] is False
    assert result["recommended_next_actions"] == []


def test_old_support_does_not_upgrade_completeness_or_edit_readiness():
    result = derive_project_answer_completeness(
        question="Explain value", context_pack=[{"content": "value"}],
        answer_available=True, intent=None,
        support_decision=SimpleNamespace(answer_supported=True, mandatory_coverage=1.0, mandatory_requirement_ids=["literal"]),
        assigned_requirement_ids=["literal"],
    )
    assert result["answer_type"] == "partial"
    assert result["answer_completeness"]["canonical_support"]["answer_supported"] is False
    assert result["answer_completeness"]["edit_ready"] is False


def test_quality_uses_syntax_not_known_commands_or_prose_noise_lists():
    assert looks_like_code_or_command("doc-atlas setup") is False
    assert looks_like_code_or_command("```sh\nunknown-command --flag\n```") is True
    assert internal_noise_score("TODO: incorrect type specification; deprecated internal parameter") == 0.0
