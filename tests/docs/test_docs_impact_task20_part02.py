"""Split tests from test_docs_impact_task20.py; shared helpers remain in the façade module."""
from tests.docs import _shared_test_docs_impact_task20 as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_hard_output_bound_invalidates_actionable_authoring_brief():
    report = {
        "schema_version": "docs-impact-2",
        "project_path": "/repo",
        "summary": {},
        "changed_files": [],
        "changed_symbols": [],
        "impacts": [{"path": f"docs/{index}.md", "evidence": "x" * 1000} for index in range(100)],
        "section_candidates": {"must_update": [], "review": [], "unlikely": []},
        "bounds": {"truncated": False, "max_output_bytes": 32 * 1024},
        "section_metadata": {},
        "authoring_brief": {
            "schema_version": "documentation-update-brief-1",
            "status": "ready_for_host_edit",
            "allowed_edits": [{"path": "docs/guide.md", "heading_path": ["Guide"]}],
            "missing_evidence": [],
            "follow_up": {"tool": "prepare_docs", "arguments_patch": {"action": "sync_project_docs"}},
        },
        "next_actions": [],
        "diff_evidence": {},
        "missing": [],
        "recommendation": "review",
        "warnings": [],
    }

    bounded = impact._bound_report(report)

    assert len(json.dumps(bounded, ensure_ascii=False).encode("utf-8")) <= 32 * 1024
    assert bounded["bounds"]["output_truncated"] is True
    assert bounded["authoring_brief"]["allowed_edits"] == []
    assert bounded["authoring_brief"]["follow_up"] == {}
    assert any(
        item["reason_code"] == "output_truncated"
        for item in bounded["authoring_brief"]["missing_evidence"]
    )


def test_markdown_preserves_unlikely_and_truncation_contract(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Overview\n\nUnrelated text.\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"])
    rendered = impact.format_docs_impact_markdown(report)

    assert report["section_candidates"]["unlikely"]
    assert "Unlikely to require an update" in rendered
    assert "### Review\n" not in rendered
    assert report["recommendation"].startswith("No maintained documentation changes")


def test_candidate_offset_produces_a_progressing_continuation(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    for index in range(12):
        (docs / f"section-{index:02d}.md").write_text("# API\n\nUse `ChangedSymbol`.\n", encoding="utf-8")

    first = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["ChangedSymbol"], candidate_limit=5)
    second = analyze_docs_impact(
        root,
        ["src/change.py"],
        changed_symbols=["ChangedSymbol"],
        candidate_offset=5,
        candidate_limit=5,
    )

    first_paths = {item["path"] for item in first["section_candidates"]["must_update"]}
    second_paths = {item["path"] for item in second["section_candidates"]["must_update"]}
    assert len(first_paths) == len(second_paths) == 5
    assert first_paths.isdisjoint(second_paths)
    assert "--candidate-offset 5" in first["bounds"]["continuation"]
    assert f"--project-path {root}" in first["bounds"]["continuation"]
    assert "--changed-symbol ChangedSymbol" in first["bounds"]["continuation"]
    assert "prepare_docs" not in first["bounds"]["continuation"]
    assert first["authoring_brief"]["allowed_edits"] == []
    assert second["authoring_brief"]["allowed_edits"] == []
    assert second["authoring_brief"]["follow_up"] == {}


def test_continuation_stops_at_candidate_evaluation_ceiling(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    body = "\n".join(f"## S{index}\nUse `ChangedSymbol`." for index in range(3))
    for index in range(4):
        (docs / f"section-{index}.md").write_text(f"# API\n{body}\n", encoding="utf-8")
    monkeypatch.setattr(impact, "_MAX_SECTION_CANDIDATES_EVALUATED", 10)

    report = analyze_docs_impact(
        root,
        ["src/change.py"],
        changed_symbols=["ChangedSymbol"],
        candidate_offset=10,
        candidate_limit=5,
    )

    assert report["bounds"]["candidate_evaluation_truncated"] is True
    assert report["bounds"]["section_candidates_returned"] == 0
    assert report["bounds"]["continuation"] is None
    assert report["bounds"]["continuation_reason"] == "evaluation_budget_exhausted_narrow_diff"


def test_continuation_preserves_config_and_cli_flags(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    for index in range(3):
        (docs / f"section-{index}.md").write_text("# API\nUse `ChangedSymbol`.\n", encoding="utf-8")
    config_path = tmp_path / "custom.yaml"
    context = {"project_path": str(root), "config_path": str(config_path), "fail_on_missing": True}

    report = analyze_docs_impact(
        root,
        ["src/change.py"],
        changed_symbols=["ChangedSymbol"],
        candidate_limit=1,
        continuation_context=context,
    )

    command = report["bounds"]["continuation"]
    assert f"--project-path {root}" in command
    assert f"--config {config_path}" in command
    assert "--changed-symbol ChangedSymbol" in command
    assert "--fail-on-missing" in command


def test_distant_symbol_section_outranks_nearby_irrelevant_section(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Nearby\n\nGeneral source notes.\n", encoding="utf-8")
    (root / "docs" / "distant.md").write_text("# Exact API\n\nUse `ChangedSymbol`.\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["ChangedSymbol"])

    assert report["section_candidates"]["must_update"][0]["path"] == "docs/distant.md"
    assert report["section_candidates"]["must_update"][0]["reason_code"] == "section_reference_changed_symbol"
    assert report["section_candidates"]["unlikely"][0]["path"] == "README.md"
    assert report["section_candidates"]["unlikely"][0]["reason_code"] == "no_explicit_reference_match"


def test_labeled_30_change_corpus_meets_precision_and_recall_gate(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    sections = ["# Impact"]
    for index in range(1, 31):
        sections.extend(["", f"## ChangedSymbol{index:02d}", f"Use `ChangedSymbol{index:02d}`."])
    (docs / "impact.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    corpus_path = Path(__file__).resolve().parents[2] / "eval" / "docs_impact" / "section_impact_corpus.json"
    cases = json.loads(corpus_path.read_text(encoding="utf-8"))

    quality = evaluate_labeled_section_impact(root, cases)

    assert quality["cases"] == 30
    assert quality["must_update_recall"] >= 0.90
    assert quality["must_update_precision"] >= 0.75
    assert quality["passed"] is True
    assert quality["automatic_symbol_cases"] == 27
    assert quality["conservative_fallback_cases"] == 3
    assert quality["fallback_review_expected"] == 3
    assert quality["fallback_review_matched"] == 3
    assert quality["fallback_review_precision"] >= 0.75
    assert quality["fallback_review_recall"] >= 0.90


def test_actual_git_pipeline_handles_30_change_quality_corpus(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    sections = ["# Impact"]
    for index in range(1, 31):
        sections.extend(["", f"## ChangedSymbol{index:02d}", f"Use `ChangedSymbol{index:02d}`."])
        if index <= 9:
            path = root / f"change_{index:02d}.py"
            old_line = f"def OldSymbol{index:02d}():\n    return 1\n"
        elif index <= 18:
            path = root / f"change_{index:02d}.ts"
            old_line = f"export class OldSymbol{index:02d} {{}}\n"
        elif index <= 27:
            path = root / f"change_{index:02d}.dart"
            old_line = f"class OldSymbol{index:02d} {{}}\n"
        else:
            internal = root / "internal"
            internal.mkdir(exist_ok=True)
            path = internal / f"change_{index:02d}.go"
            old_line = f"func OldSymbol{index:02d}() {{}}\n"
        path.write_text(old_line, encoding="utf-8")
    (docs / "impact.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    for index in range(1, 31):
        if index <= 9:
            path = root / f"change_{index:02d}.py"
            new_line = f"def ChangedSymbol{index:02d}():\n    return 1\n"
        elif index <= 18:
            path = root / f"change_{index:02d}.ts"
            new_line = f"export class ChangedSymbol{index:02d} {{}}\n"
        elif index <= 27:
            path = root / f"change_{index:02d}.dart"
            new_line = f"class ChangedSymbol{index:02d} {{}}\n"
        else:
            path = root / "internal" / f"change_{index:02d}.go"
            new_line = f"func ChangedSymbol{index:02d}() {{}}\n"
        path.write_text(new_line, encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "change corpus")

    evidence = changed_evidence_from_git(root, base)
    report = analyze_docs_impact(root, evidence["paths"], diff_evidence=evidence)

    must_update_headings = {
        " > ".join(item["heading_path"])
        for item in report["section_candidates"]["must_update"]
    }
    assert len(must_update_headings) == 27
    assert evidence["diagnostics"]["symbol_confidence"] == "low"
    assert len(evidence["diagnostics"]["fallback_paths"]) == 3
    assert any(item["reason_code"] == "diff_symbol_parser_fallback" for item in report["section_candidates"]["review"])
