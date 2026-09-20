import pytest

from tests.docs._global_evidence_fixtures import capture_fixture, visible


@pytest.mark.parametrize("value,error", [(17, "LeaseExpired"), (29, "WaitExpired")])
def test_separate_default_and_exception_survive_long_root(tmp_path, value, error):
    docs = {
        "default.md": (
            "# LeaseClient\n\n"
            f"The default timeout is {value} seconds.\n"
        ),
        "error.md": (
            "# LeaseClient\n\n"
            f"An expired operation raises `{error}`.\n"
        ),
        "overview.md": (
            "# Overview\n\n"
            "LeaseClient default timeout duration requests exception operation behavior documentation.\n"
        ),
    }
    capture = capture_fixture(
        tmp_path, docs,
        "What is LeaseClient default timeout duration for requests and "
        "which exception is raised when an operation expires?",
    )
    text = visible(capture)
    assert f"{value} seconds" in text
    assert error in text


def test_need_local_admission_does_not_accept_full_keyword_distractor(tmp_path):
    capture = capture_fixture(
        tmp_path,
        {
            "facts.md": (
                "# LeaseClient\n\n"
                "The default timeout is 17 seconds.\n\n"
                "An expired operation raises `LeaseExpired`.\n"
            ),
            "noise.md": (
                "# LeaseClient default timeout exception behavior\n\n"
                "This overview discusses LeaseClient default timeout and exception behavior.\n"
            ),
        },
        "What is LeaseClient default timeout and which exception is raised?",
    )
    text = visible(capture)
    assert "17 seconds" in text
    assert "LeaseExpired" in text


def test_need_local_admission_keeps_subject_binding(tmp_path):
    capture = capture_fixture(
        tmp_path,
        {
            "lease.md": "# LeaseClient\n\nThe default timeout is 17 seconds.\n",
            "other.md": "# OtherClient\n\nThe default timeout is 99 seconds.\n",
        },
        "What is LeaseClient default timeout?",
    )
    text = visible(capture)
    assert "17 seconds" in text
    assert "99 seconds" not in text


def test_need_local_admission_does_not_fabricate_missing_second_need(tmp_path):
    capture = capture_fixture(
        tmp_path,
        {"lease.md": "# LeaseClient\n\nThe default timeout is 17 seconds.\n"},
        "What is LeaseClient default timeout and which exception is raised?",
    )
    text = visible(capture)
    assert "17 seconds" in text
    assert "raises" not in text


def test_typed_need_proof_allows_subject_bound_elsewhere_in_same_source_span():
    from docmancer.docs.application.retrieval_need_support import retrieval_need_local_witness

    text = (
        "NETKIT enforces timeouts everywhere.\n\n"
        "The default behavior is to raise `WaitExpired` after 23 seconds of inactivity."
    )
    source = {"title": "Timeouts", "authority": "source_of_truth"}
    default = {
        "query_id": "query-need-default", "query_origin": "retrieval_need",
        "text": "What is NETKIT default timeout behavior", "need_subject": "NETKIT",
        "need_relation": "default", "need_context": None,
    }
    exception = {
        "query_id": "query-need-exception", "query_origin": "retrieval_need",
        "text": "What is NETKIT default timeout behavior which exception?",
        "need_subject": "NETKIT", "need_relation": "exception",
        "need_context": "What is NETKIT default timeout behavior",
    }
    assert retrieval_need_local_witness(default, text, source=source) is True
    assert retrieval_need_local_witness(exception, text, source=source) is True


def test_requirement_need_uses_normative_relation_not_keyword_overlap():
    from docmancer.docs.application.retrieval_need_support import retrieval_need_local_witness

    query = {
        "query_id": "query-need-requirement", "query_origin": "retrieval_need",
        "text": "are blank lines around a table required?", "need_subject": "blank",
        "need_relation": "requirement", "need_context": None,
    }
    assert retrieval_need_local_witness(
        query,
        "Additionally, a table must be surrounded by blank lines. There must be a blank line after it.",
        source={"title": "Tables", "authority": "source_of_truth"},
    ) is True
    assert retrieval_need_local_witness(
        query,
        "This section discusses blank lines around tables.",
        source={"title": "Tables", "authority": "source_of_truth"},
    ) is False


def test_disabled_behavior_need_accepts_not_enabled_but_rejects_enabled_state():
    from docmancer.docs.application.retrieval_need_support import retrieval_need_local_witness

    query = {
        "query_id": "query-need-behavior", "query_origin": "retrieval_need",
        "text": "What happens to preview-switch when preview mode is disabled?",
        "need_subject": "preview-switch", "need_relation": "behavior", "need_context": None,
    }
    assert retrieval_need_local_witness(
        query,
        "preview-switch = true. If preview mode is not enabled, this setting has no effect.",
        source={"title": "Preview settings", "authority": "source_of_truth"},
    ) is True
    assert retrieval_need_local_witness(
        query,
        "preview-switch = true. When preview mode is enabled, configure this setting explicitly.",
        source={"title": "Preview settings", "authority": "source_of_truth"},
    ) is False


def test_single_typed_need_keeps_internal_probe_even_when_text_equals_root():
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan

    plan = build_documentation_query_plan(
        "What happens to preview-switch when preview mode is disabled?"
    )
    needs = [query for query in plan.queries if query.origin == "retrieval_need"]
    assert len(needs) == 1
    assert needs[0].need_relation == "behavior"
    assert needs[0].text == "What happens to preview-switch when preview mode is disabled?"
