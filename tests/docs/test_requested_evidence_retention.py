from tests.docs._global_evidence_fixtures import capture_fixture, visible


def _before(capture):
    return capture["projection_attempts"][0]["before_projection"]


def _context_text(capture):
    return "\n".join(
        str(row.get("content") or row.get("display_text") or row.get("snippet") or "")
        for row in _before(capture).get("context_pack") or []
    )


def test_restriction_and_blank_line_requirement_both_survive(tmp_path):
    docs = {"grid.md": (
        "# GridTables\n\n"
        "Cells must not contain block elements or multiple lines.\n\n"
        "Blank lines before and after a table are required.\n"
    )}
    capture = capture_fixture(
        tmp_path, docs,
        "Can GridTables cells contain block elements or multiple lines, "
        "and are blank lines around a table required?",
    )
    retrieved = _context_text(capture)
    assert "must not contain block elements or multiple lines" in retrieved
    assert "Blank lines before and after a table are required" in retrieved
    text = visible(capture)
    assert "must not contain block elements or multiple lines" in text
    assert "Blank lines before and after a table are required" in text


def test_requested_condition_wins_over_opposite_configuration_example(tmp_path):
    docs = {"preview.md": (
        "# RuleSwitch\n\n"
        "If preview mode is not enabled, RuleSwitch has no effect.\n\n"
        "If preview mode is enabled, configure RuleSwitch in the settings.\n"
    )}
    capture = capture_fixture(
        tmp_path, docs,
        "What happens to RuleSwitch when preview mode is not enabled?",
    )
    retrieved = _context_text(capture)
    assert "RuleSwitch has no effect" in retrieved
    assert "configure RuleSwitch" in retrieved
    text = visible(capture)
    assert "RuleSwitch has no effect" in text


def test_three_short_requested_sources_beat_long_topical_paragraph(tmp_path):
    docs = {
        "a.md": "# RelayClient\n\nThe default timeout is 11 seconds.\n",
        "b.md": "# RelayClient\n\nThe exception raised after expiration is `RelayExpired`.\n",
        "c.md": "# RelayClient\n\nThe required retry count is 3.\n",
        "noise.md": "# RelayClient overview\n\n" + (
            "RelayClient timeout exception retries requests behavior configuration overview. " * 12
        ) + "\n",
    }
    capture = capture_fixture(
        tmp_path, docs,
        "What is RelayClient default timeout, which exception is raised, "
        "and which retry count is required?",
    )
    text = visible(capture)
    assert "11 seconds" in text
    assert "RelayExpired" in text
    assert "retry count is 3" in text
