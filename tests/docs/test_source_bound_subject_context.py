from tests.docs._global_evidence_fixtures import capture_fixture, visible


def test_owning_subject_and_exception_rule_reach_the_public_packet(tmp_path):
    docs = {"tasks.md": (
        "# QueueTasks\n\n"
        "QueueTasks groups task functions.\n\n"
        "Tasks execute in order. If one raises an exception, "
        "later tasks are not executed.\n"
    )}
    capture = capture_fixture(
        tmp_path, docs,
        "If one QueueTasks function raises an exception, "
        "what happens to later tasks and their ordering?",
    )
    text = visible(capture)
    assert "Tasks execute in order." in text
    assert "later tasks are not executed" in text
    assert "QueueTasks" in text


def test_sibling_subject_does_not_authorize_other_task_rule(tmp_path):
    docs = {"tasks.md": (
        "# QueueTasks\n\nQueueTasks groups task functions.\n\n"
        "## OtherTasks\n\nTasks execute in order. If one raises an exception, later tasks stop.\n"
    )}
    capture = capture_fixture(
        tmp_path, docs,
        "If one QueueTasks function raises an exception, what happens to later tasks?",
    )
    text = visible(capture)
    assert not ("OtherTasks" in text and "later tasks stop" in text)


def test_navigation_heading_alone_does_not_authorize_subject(tmp_path):
    docs = {"tasks.md": (
        "# QueueTasks\n\n- [Ordering](ordering.md)\n- [Exceptions](errors.md)\n"
    )}
    capture = capture_fixture(
        tmp_path, docs,
        "If one QueueTasks function raises an exception, what happens to later tasks?",
    )
    assert "later tasks" not in visible(capture)
