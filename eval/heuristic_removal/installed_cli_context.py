"""Verify installed CLI context against the completed isolated stdio fixture."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import database, files, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.work.resolve()
    project = root / "project"
    storage = root / "docatlas_home/mcp-members/members.db"
    import docmancer
    assert Path(docmancer.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert not args.output.exists()
    args.output.mkdir(parents=True)
    config = root / "cli-config.json"
    config.write_text(json.dumps({"index": {"db_path": str(storage)},
                                 "retrieval": {"default_mode": "lexical"}}))
    env = {key: os.environ[key] for key in ("PATH", "TIKTOKEN_CACHE_DIR") if key in os.environ}
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "DOCATLAS_HOME"):
        env[key] = str(root / key.lower())
    env.update(DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0", HF_HUB_OFFLINE="1")
    before = database(storage), files(project)
    save(args.output / "before.json", before)
    result = subprocess.run([
        str(Path(sys.executable).parent / "doc-atlas"), "context", str(project),
        "How do I authenticate with OAuth tokens?", "--config", str(config),
        "--mode", "project-only", "--format", "json",
    ], env=env, cwd=root, capture_output=True, text=True, timeout=90)
    (args.output / "stdout.json").write_text(result.stdout)
    (args.output / "stderr.log").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["answer_available"] is False
    assert payload["answer_completeness"]["edit_ready"] is False
    rows = payload["context_pack"]
    assert any("Authenticate with OAuth tokens." in str(row.get("content") or row.get("snippet") or "") for row in rows)
    after = database(storage), files(project)
    save(args.output / "after.json", after)
    assert after == before
    save(args.output / "SUMMARY.json", {"status": "PASS", "boundary": "installed CLI, real prepared SQLite", "origin": docmancer.__file__})


if __name__ == "__main__":
    main()
