from __future__ import annotations

import subprocess
from pathlib import Path

from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from tests._shared_test_docs_service import _flutter_project, _service_with_real_agent


def _commit_project(project: Path) -> str:
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.name", "Tests"], check=True)
    subprocess.run(["git", "-C", str(project), "add", "."], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-qm", "accepted docs"], check=True)
    return subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


