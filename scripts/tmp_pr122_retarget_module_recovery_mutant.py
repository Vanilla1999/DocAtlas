from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts/run_agent_developer_adversarial_mutation_gate.py"

OLD = '''    Mutant(
        "module_recovery_reason_projection_guard",
        "docmancer/docs/interfaces/mcp/context_tools.py",
        "_MODULE_RECOVERY_REASON_CODES = frozenset({\\n    \\\"module_ambiguous\\\", \\\"module_not_found\\\", \\\"no_module_docs\\\",\\n})",
        "_MODULE_RECOVERY_REASON_CODES = frozenset({\\n    \\\"module_not_found\\\", \\\"no_module_docs\\\",\\n})  # mutation: hide ambiguous-module recovery metadata",
        FULL_GATE,
    ),
'''

NEW = '''    Mutant(
        "module_recovery_reason_projection_guard",
        "docmancer/docs/interfaces/mcp/recovery_projection.py",
        "_MODULE_RECOVERY_REASON_CODES = frozenset({\\n    \\\"module_ambiguous\\\", \\\"module_not_found\\\", \\\"no_module_docs\\\",\\n})",
        "_MODULE_RECOVERY_REASON_CODES = frozenset({\\n    \\\"module_not_found\\\", \\\"no_module_docs\\\",\\n})  # mutation: hide ambiguous-module recovery metadata",
        FULL_GATE,
    ),
'''


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise SystemExit("module recovery mutation target drifted")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")

    run("python", "-m", "compileall", "-q", "docmancer", "scripts", "tests")
    run("python", "scripts/check_python_module_size.py")
    run("python", "scripts/run_agent_developer_adversarial_gate.py")
    run("python", "scripts/run_agent_developer_adversarial_mutation_gate.py")

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", str(TARGET.relative_to(ROOT)))
    run("git", "commit", "-m", "test: retarget module recovery mutation guard")
    run("git", "push", "origin", "HEAD:p0/recoverable-docs-failures")


if __name__ == "__main__":
    main()
