from tests.docs._reference_binding_fixtures import capture_reference_case, visible


def test_verified_owner_supports_its_warning(tmp_path):
    cap = capture_reference_case(tmp_path, {"Tasks.md":
        "# QueueTasks\n\nQueueTasks groups task functions.\n\nTasks execute in order. If one raises an exception, later tasks stop.\n"
    }, "In the file Tasks, if one QueueTasks function raises an exception, what happens to later tasks and their ordering?")
    assert "execute in order" in visible(cap) and "later tasks stop" in visible(cap)


