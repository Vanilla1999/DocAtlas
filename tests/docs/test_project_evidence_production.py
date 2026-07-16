from __future__ import annotations

from pathlib import Path

from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.domain.project_evidence import classify_project_evidence
from docmancer.docs.domain.project_state import create_project_docs_next_action
from docmancer.docs.models import ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata


QUESTION = "Explain the architecture"


class ProductionGapFacade:
    def read_project_metadata(self, project_path: str) -> ProjectMetadata:
        return ProjectMetadata(project_path=project_path)

    def get_project_docs(self, project_path: str, question: str, **_kwargs) -> ProjectDocsResult:
        return ProjectDocsResult(
            project_path=project_path,
            query=question,
            results=[],
            answer_available=False,
        )

    def inspect_project_docs(self, project_path: str) -> ProjectDocsInspectResult:
        root = Path(project_path)
        action = create_project_docs_next_action(root, QUESTION)
        return ProjectDocsInspectResult(
            project_detected=True,
            project_path=project_path,
            reason_code="no_project_docs",
            recommended_next_actions=[action],
        )


def _write_project(root: Path, *, runtime_config: bool = True, manifest_only: bool = False) -> None:
    (root / "pyproject.toml").write_text(
        """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "evidence-demo"
version = "0.1.0"

[project.scripts]
evidence-demo = "demo.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
""".strip() + "\n",
        encoding="utf-8",
    )
    if manifest_only:
        return
    package = root / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .service import run\n", encoding="utf-8")
    config_line = '    port = os.getenv("DEMO_PORT", "8080")\n' if runtime_config else '    port = "8080"\n'
    (package / "main.py").write_text(
        "import os\nfrom demo.service import run\n\ndef main():\n" + config_line + "    return run(port)\n",
        encoding="utf-8",
    )
    (package / "service.py").write_text(
        "def run(port):\n    return {\"port\": port}\n",
        encoding="utf-8",
    )


def _production_gap(root: Path) -> dict:
    result = ProjectContextService(ProductionGapFacade()).get_project_context(
        str(root), QUESTION, mode="project-only", limit=8,
    )
    action = next(item for item in result.next_actions if item.get("action") == "create_reviewable_project_doc")
    return action["documentation_gap"]


def test_complete_small_project_is_complete_through_production_handoff(tmp_path):
    _write_project(tmp_path)

    gap = _production_gap(tmp_path)

    assert gap["evidence_complete"] is True
    assert {section["state"] for section in gap["required_sections"]} == {"complete"}
    categories = {item["category"] for item in gap["evidence_to_collect"]}
    assert categories == {
        "manifests", "root entrypoints", "entrypoints", "runtime configuration",
        "module directories", "module imports", "test and build configuration",
    }
    assert all(item["facts"] for item in gap["evidence_to_collect"])


def test_project_without_runtime_configuration_keeps_runtime_flow_partial(tmp_path):
    _write_project(tmp_path, runtime_config=False)

    gap = _production_gap(tmp_path)
    sections = {section["name"]: section for section in gap["required_sections"]}

    assert gap["evidence_complete"] is False
    assert sections["runtime flow"]["state"] == "partial"
    assert sections["runtime flow"]["missing_evidence"] == ["runtime configuration"]


def test_manifest_only_project_stays_incomplete_through_production_handoff(tmp_path):
    _write_project(tmp_path, manifest_only=True)

    gap = _production_gap(tmp_path)
    sections = {section["name"]: section for section in gap["required_sections"]}

    assert gap["evidence_complete"] is False
    assert sections["runtime flow"]["state"] == "missing"
    assert sections["modules"]["state"] == "missing"
    assert not any(item["category"] in {"root entrypoints", "entrypoints"} for item in gap["evidence_to_collect"])


def test_source_filename_alone_does_not_prove_entrypoint_or_runtime_config(tmp_path):
    _write_project(tmp_path, manifest_only=True)
    (tmp_path / "main.py").write_text("VALUE = 'runtime configuration'\n", encoding="utf-8")

    gap = _production_gap(tmp_path)
    categories = {item["category"] for item in gap["evidence_to_collect"]}

    assert "entrypoints" not in categories
    assert "runtime configuration" not in categories


def test_gap_recovery_reports_repo_map_overflow_in_host_diagnostics(tmp_path):
    _write_project(tmp_path, manifest_only=True)
    package = tmp_path / "src" / "many_modules"
    package.mkdir(parents=True)
    for index in range(20):
        (package / f"module_{index}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8",
        )

    result = ProjectContextService(ProductionGapFacade()).get_project_context(
        str(tmp_path), QUESTION, mode="project-only", limit=8,
    )
    stage = result.diagnostics["retrieval_routing"]["stages"]["repo_map"]

    assert stage["observed_item_count"] > stage["item_count"]
    assert stage["budget_exceeded"] is True
    assert stage["status"] == "insufficient"
    assert "retrieval_stage_budget_exceeded" in result.warnings


def test_non_python_runtime_detection_ignores_comments_and_strings(tmp_path):
    path = tmp_path / "app.js"
    path.write_text(
        "// process.env.COMMENT_ONLY\nconst example = 'process.env.STRING_ONLY';\n",
        encoding="utf-8",
    )

    evidence = classify_project_evidence(
        tmp_path,
        repo_map=[{"path": "app.js", "symbols": []}],
        code_graph=None,
    )

    assert "runtime configuration" not in {item["category"] for item in evidence}


def test_non_python_runtime_detection_keeps_executable_access(tmp_path):
    path = tmp_path / "app.js"
    path.write_text("const port = process.env.DEMO_PORT;\n", encoding="utf-8")

    evidence = classify_project_evidence(
        tmp_path,
        repo_map=[{"path": "app.js", "symbols": []}],
        code_graph=None,
    )

    assert "runtime configuration" in {item["category"] for item in evidence}
