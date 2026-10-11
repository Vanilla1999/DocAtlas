import os

import pytest

from docmancer.mcp import credentials, paths


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path))
    paths.ensure_dirs()
    paths.secrets_dir().mkdir(exist_ok=True)

















