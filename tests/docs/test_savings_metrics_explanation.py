from __future__ import annotations

from docmancer.docs.application.project_context_service import project_context_metrics
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult


def test_savings_metrics_explain_not_relevance_score():
    docs = ProjectDocsResult(project_path="/repo", query="q", results=[ProjectDocsChunk(title="Readme", content="Useful project documentation content with enough words to pass quality filtering.", source="README.md", url=None, path="README.md", metadata={"raw_tokens": 1000, "savings_percent": 95.0})])
    pack = [{"source_class": "project_doc", "path": "README.md", "token_estimate": 20, "content": "Useful project documentation content with enough words to pass quality filtering."}]

    metrics = project_context_metrics(context_pack=pack, project_docs=docs, dependency_docs=None)

    assert metrics["token_savings"]["meaning"] == "compression_vs_raw_docs_not_relevance_score"


def test_quality_metrics_include_filtered_and_demoted_counts():
    docs = ProjectDocsResult(project_path="/repo", query="q", results=[
        ProjectDocsChunk(title="One", content="Useful project documentation content with enough words to pass quality filtering.", source="README.md", url=None, path="README.md"),
        ProjectDocsChunk(title="Two", content="TODO: remove when discarding this internal parameter. type: ignore", source="docs/source.md", url=None, path="docs/source.md"),
    ])
    pack = [{"source_class": "project_doc", "path": "README.md", "token_estimate": 20, "content": "Useful project documentation content with enough words to pass quality filtering."}]

    metrics = project_context_metrics(context_pack=pack, project_docs=docs, dependency_docs=None)

    assert metrics["quality"]["trivial_sections_filtered"] == 1
    assert metrics["quality"]["noise_sections_demoted"] == 1
