import json

import pytest

from docmancer.core.product_identity import PRODUCT_ID, STATE_OWNER_FILENAME
from docmancer.mcp import paths


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path))
    paths.ensure_dirs()







