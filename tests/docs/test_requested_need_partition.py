import pytest

from docmancer.docs.domain.question_plan import retrieval_needs


@pytest.mark.parametrize("subject", ["LeaseClient", "StoreClient", "QueueClient"])
def test_default_and_exception_are_two_question_bound_needs(subject):
    question = f"What is {subject} default timeout and which exception is raised?"
    needs = retrieval_needs(question)
    assert len(needs) == 2
    for need in needs:
        assert question[need.query_span_start:need.query_span_end] == need.query_span_text
        assert need.subject == subject
    assert {need.relation for need in needs} == {"default", "exception"}
    assert all("TimeoutException" not in need.query_span_text for need in needs)


def test_shared_condition_is_not_dropped_from_the_second_need():
    question = (
        "When preview is not enabled, what is RuleSwitch behavior "
        "and which configuration is used?"
    )
    needs = retrieval_needs(question)
    assert len(needs) == 2
    assert all("preview is not enabled" in need.context for need in needs)
    assert all(need.subject == "RuleSwitch" for need in needs)


def test_how_and_why_preserve_mechanism_and_reason_without_inventing_reason():
    question = "How does Resolver restrict candidates across indexes and why?"
    needs = retrieval_needs(question)
    assert [need.relation for need in needs] == ["mechanism", "reason"]
    assert all(need.subject == "Resolver" for need in needs)
    assert all("security" not in need.query_span_text.casefold() for need in needs)


def test_comparison_exposes_both_sides_without_claiming_full_answer():
    question = "What is the difference between a truncated response and insufficient evidence?"
    needs = retrieval_needs(question)
    assert len(needs) == 2
    assert {need.relation for need in needs} == {"comparison_side"}
    assert {need.subject for need in needs} == {"truncated response", "insufficient evidence"}


def test_quoted_and_does_not_create_two_needs():
    needs = retrieval_needs("What does `read and write` mean?")
    assert len(needs) <= 1


def test_or_alternatives_do_not_become_two_mandatory_needs():
    needs = retrieval_needs("Can CacheClient use memory or disk storage?")
    assert len(needs) <= 1


def test_elided_default_clause_reuses_previous_concrete_subject():
    question = (
        'Can allow_credentials work with allow_origins=["*"] in CORSMiddleware, '
        'and what is the default?'
    )
    needs = retrieval_needs(question)
    assert len(needs) == 2
    assert needs[0].relation == "restriction"
    assert needs[1].relation == "default"
    assert needs[1].subject == "allow_credentials"


def test_which_default_clause_binds_embedded_actor_and_escape_hatch_inherits_it():
    question = (
        "Which build isolation mode does ToolRunner use by default "
        "and what is the escape hatch for a missing build dependency?"
    )
    needs = retrieval_needs(question)
    assert len(needs) == 2
    assert needs[0].relation == "default"
    assert needs[0].subject == "ToolRunner"
    assert needs[1].subject == "ToolRunner"
    assert "build isolation mode" in needs[1].context.casefold()


def test_happens_to_behavior_binds_setting_subject_and_state():
    question = "What happens to RuleSwitch when preview mode is disabled?"
    needs = retrieval_needs(question)
    assert len(needs) == 1
    assert needs[0].relation == "behavior"
    assert needs[0].subject == "RuleSwitch"
    assert "disabled" in needs[0].query_span_text.casefold()


def test_elided_exception_inherits_previous_timeout_context():
    question = "What is NetClient default timeout behavior: how long and which exception?"
    needs = retrieval_needs(question)
    exception = next(need for need in needs if need.relation == "exception")
    assert exception.subject == "NetClient"
    assert "timeout" in exception.context.casefold()


def test_which_default_clause_binds_lowercase_actor_after_does():
    needs = retrieval_needs(
        "Which build isolation mode does toolrunner use by default "
        "and what is the escape hatch for a missing build dependency?"
    )
    assert [need.subject for need in needs] == ["toolrunner", "toolrunner"]


def test_happens_to_binds_hyphenated_setting_without_camelcase():
    needs = retrieval_needs("What happens to preview-switch when preview mode is disabled?")
    assert len(needs) == 1
    assert needs[0].subject == "preview-switch"
    assert needs[0].relation == "behavior"


def test_new_sentence_is_not_appended_to_previous_exception_need():
    question = "What is NetClient default timeout behavior: how long and which exception? Also identify the exact value chosen in our private deployment."
    needs = retrieval_needs(question)
    exception = next(need for need in needs if need.relation == "exception")
    assert "deployment" not in exception.query_span_text
    assert "timeout" in exception.context
    assert all(question[n.query_span_start:n.query_span_end] == n.query_span_text for n in needs)


def test_sentence_mark_inside_quoted_symbol_does_not_split():
    needs = retrieval_needs('What does `Why? Who?` mean?')
    assert len(needs) <= 1
