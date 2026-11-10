"""Real one-line installer registration: execute its shell function, not a mock."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def register(src: str, config: Path) -> str:
    first = "register_opencode() {"
    final = '\n}\n\nif [ -n "$SELECTION" ]'
    assert src.count(first) == src.count(final) == 1
    body = src.split(first, 1)[1].split(final, 1)[0]
    shell = '''
set -eu
SERVER_NAME=docatlas-docs
pick_python() { printf '%s\\n' "$TEST_PYTHON"; }
ok() { printf '%s\\n' "$*"; }
warn() { printf '%s\\n' "$*" >&2; }
step() { printf '%s\\n' "$*"; }
register_opencode() {
''' + body + '''
}
register_opencode
'''
    env = {key: value for key, value in os.environ.items() if key in
           {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    env.update(TEST_PYTHON=sys.executable, OPENCODE_CONFIG=str(config), HOME=str(config.parent))
    result = subprocess.run(["sh", "-c", shell], env=env, capture_output=True,
                            text=True, timeout=30, check=True)
    return result.stdout + result.stderr


def main(script: Path, out: Path):
    src = script.read_text(encoding="utf-8")
    registration_calls = 0

    def run_registration(config: Path) -> str:
        nonlocal registration_calls
        registration_calls += 1
        return register(src, config)

    with tempfile.TemporaryDirectory(prefix="docatlas-shell-registration-") as td:
        root = Path(td)
        path = root / "fresh.json"
        run_registration(path)
        entry = json.loads(path.read_text())["mcp"]["servers"]["docatlas-docs"]
        assert entry["environment"] == {
            "DOCATLAS_MCP_TEXT_FALLBACK": "1", "DOCATLAS_MCP_COMPACT_TEXT": "1",
            "DOCATLAS_CONTEXT_COMPRESSION": "off"}
        frozen = path.read_bytes()
        run_registration(path)
        assert path.read_bytes() == frozen

        path = root / "existing.json"
        # Registration carries this path without reading or loading model assets.
        model_path = str(root / "model-not-loaded")
        path.write_text(json.dumps({"mcp": {"docatlas": {
            "type": "local", "command": ["doc-atlas", "mcp", "docs-serve"],
            "enabled": False,
            "environment": {"DOCATLAS_MCP_TEXT_FALLBACK": "1", "CUSTOM": "keep",
                            "DOCATLAS_MINILM_MODEL_DIR": model_path}}}}))
        run_registration(path)
        current = json.loads(path.read_text())["mcp"]
        assert "docatlas" not in current
        updated = current["servers"]["docatlas"]
        assert updated["disabled"] is True
        assert updated["environment"]["CUSTOM"] == "keep"
        assert updated["environment"]["DOCATLAS_MCP_COMPACT_TEXT"] == "1"
        assert updated["environment"]["DOCATLAS_MINILM_MODEL_DIR"] == model_path
        assert updated["environment"]["DOCATLAS_CONTEXT_COMPRESSION"] == "off"
        frozen = path.read_bytes()
        run_registration(path)
        assert path.read_bytes() == frozen

        path = root / "explicit.json"
        explicit_environment = {
            "DOCATLAS_MINILM_MODEL_DIR": model_path,
            "DOCATLAS_CONTEXT_COMPRESSION": "minilm-sections-v1",
            "DOCATLAS_CONTEXT_ASSEMBLY": "literal", "CUSTOM": "keep",
        }
        path.write_text(json.dumps({"mcp": {"servers": {"my-docs": {
            "type": "local", "command": ["doc-atlas", "mcp", "docs-serve"],
            "disabled": True, "environment": explicit_environment}}}}))
        run_registration(path)
        servers = json.loads(path.read_text())["mcp"]["servers"]
        assert set(servers) == {"my-docs"}
        assert servers["my-docs"]["disabled"] is True
        assert servers["my-docs"]["environment"] == {
            **explicit_environment,
            "DOCATLAS_MCP_TEXT_FALLBACK": "1", "DOCATLAS_MCP_COMPACT_TEXT": "1"}
        frozen = path.read_bytes()
        run_registration(path)
        assert path.read_bytes() == frozen

        path = root / "unsafe.json"
        path.write_text(json.dumps({"mcp": {"servers": {"docatlas": {
            "type": "local", "command": ["doc-atlas", "mcp", "docs-serve"],
            "environment": {"DOCATLAS_MCP_MODEL_VIEW": "1"}}}}}))
        before = path.read_bytes()
        warning = run_registration(path)
        assert path.read_bytes() == before and "private MCP model view" in warning

        path = root / "commented.json"
        path.write_text('{ "mcp": { "servers": {} }, // keep comment\n "theme": "dark", }')
        before = path.read_bytes()
        warning = run_registration(path)
        assert path.read_bytes() == before
        assert "JSONC update requires manual editing" in warning
        assert "DOCATLAS_MCP_COMPACT_TEXT" in warning
        assert "DOCATLAS_CONTEXT_COMPRESSION" in warning
        assert "use compression=off only when unset" in warning

        out.mkdir(parents=True, exist_ok=True)
        result = {"pass": True, "real_shell_function": True,
                  "registration_calls": registration_calls, "scenarios": 5,
                  "new_registration": True, "idempotent": True,
                  "upgrades_legacy": True, "preserves_other_options": True,
                  "model_path_alone_keeps_ordinary_selection": True,
                  "preserves_explicit_compression_and_layout": True,
                  "refuses_private_meta": True, "preserves_jsonc_comments": True,
                  "full_uv_install_not_executed": True}
        (out / "INSTALLER.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    main(args.script, args.out)
