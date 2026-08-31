import json
from pathlib import Path

import pytest

from docmancer.mcp import agent_config


@pytest.mark.parametrize("environment", [[], "", 0, False, None])
def test_register_refuses_falsey_non_object_opencode_environment(tmp_path, environment):
    cfg = tmp_path / "opencode.json"
    original = {
        "mcp": {
            "docatlas": {
                "type": "local",
                "command": ["doc-atlas", "mcp", "docs-serve"],
                "environment": environment,
            }
        }
    }
    cfg.write_text(json.dumps(original))
    target = agent_config.AgentTarget("opencode", cfg, "json_opencode_mcp")

    with pytest.raises(ValueError, match="non-object environment"):
        agent_config.register_server(target)

    assert json.loads(cfg.read_text()) == original


def test_opencode_installer_rejects_falsey_non_object_environment():
    installer = Path(__file__).resolve().parents[1] / "scripts" / "install.sh"
    text = installer.read_text()

    assert 'if existing is None or "environment" not in existing:' in text
    assert 'environment = (existing or {}).get("environment") or {}' not in text
