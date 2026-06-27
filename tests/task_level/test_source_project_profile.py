from __future__ import annotations

from pathlib import Path


PROFILE = Path("eval/task_level/results/source_project_profiles/nbo.md")


def test_nbo_source_profile_exists():
    assert PROFILE.exists()


def test_nbo_source_profile_has_privacy_boundary():
    text = PROFILE.read_text(encoding="utf-8")

    assert "Sanitized real-project-derived fixture" in text
    assert "No live repository access is required" in text
    assert "No `.git`, credentials, private remotes, environment files" in text
    assert "customer/private data" in text


def test_nbo_source_profile_documents_fixture_scope():
    text = PROFILE.read_text(encoding="utf-8")

    assert "Flutter/Dart mobile application" in text
    assert "Only permission-related module excerpts" in text
    assert "full application domain details" in text
    assert "private business logic outside fixture scope" in text
