import json

import pytest

from docmancer.core.product_identity import PRODUCT_ID, STATE_OWNER_FILENAME
from docmancer.mcp import paths


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path))
    monkeypatch.delenv("DOCMANCER_HOME", raising=False)
    paths.ensure_dirs()


@pytest.mark.parametrize(
    "package, version",
    [
        ("..", "1.0"),
        ("acme", ".."),
        ("../etc", "1.0"),
        ("acme", "../../etc/passwd"),
        ("foo/../bar", "1.0"),
        ("acme", "1.0/../../../etc"),
        ("acme\\evil", "1.0"),
        ("acme", "1.0\x00bad"),
        ("/abs", "1.0"),
        ("", "1.0"),
        ("acme", " 1.0 "),
    ],
)
def test_package_dir_rejects_traversal_components(package, version):
    with pytest.raises(ValueError):
        paths.package_dir(package, version)


def test_package_dir_accepts_npm_scoped_name():
    p = paths.package_dir("@scope/pkg", "1.2.3")
    assert p.is_relative_to(paths.servers_dir().resolve())
    assert p.name == "pkg@1.2.3"


def test_package_dir_accepts_plain_spec():
    p = paths.package_dir("acme", "v1")
    assert p == paths.servers_dir().resolve() / "acme@v1"
    marker = paths.docmancer_home() / STATE_OWNER_FILENAME
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["product_id"] == PRODUCT_ID
    assert paths.docmancer_home().name != ".docmancer"


def test_secrets_env_file_rejects_traversal():
    with pytest.raises(ValueError):
        paths.secrets_env_file("../etc/passwd")
