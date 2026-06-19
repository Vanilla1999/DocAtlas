from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document


def test_cross_index_project_and_library_sources_are_retrievable(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [
            Document(
                source="project://docs/testing.md",
                content="# Testing Convention\n\nUse the local smoke-test helper before committing FastAPI changes.",
                metadata={"format": "markdown", "source_class": "project_file", "project_path": str(tmp_path)},
            ),
            Document(
                source="https://fastapi.tiangolo.com/tutorial/testing",
                content="# Testing\n\nUse fastapi.testclient.TestClient with pytest assertions.",
                metadata={"format": "markdown", "source_class": "library_docs", "library": "fastapi"},
            ),
        ],
        recreate=True,
    )

    chunks = agent.query("local smoke-test helper and FastAPI TestClient pytest assertions", limit=5)
    source_classes = {chunk.metadata.get("source_class") for chunk in chunks}

    assert "project_file" in source_classes
    assert "library_docs" in source_classes
