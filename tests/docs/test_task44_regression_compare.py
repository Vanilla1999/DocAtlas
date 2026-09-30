"""Synthetic JUnit parser/comparator units, not a product regression run."""
import pytest
from experiments.crosslingual_relevance import regression_compare as rc


def state(status, signature=None):
    return {"status": status, "failure_signature": signature, "skip_reason": None}


def manifest():
    return {key: "unit-same-value" for key in rc.COMPARABILITY_FIELDS}


def test_separate_new_existing_skipped_missing_and_changed():
    old = {"new": state("passed"), "old": state("failure", "a"), "changed": state("failure", "a"),
        "fixed": state("failure", "a"), "missing": state("passed"), "skip": state("passed")}
    new = {"new": state("failure", "x"), "old": state("failure", "a"), "changed": state("error", "b"),
        "fixed": state("passed"), "skip": state("skipped"), "added": state("failure", "z")}
    result = rc.compare(old, new, manifest(), manifest())
    for key in ("new_failures_on_previously_passed_tests", "existing_identical_failures",
        "existing_tests_with_changed_failure", "fixed_failures", "candidate_missing",
        "candidate_skipped", "new_tests_failing"):
        assert result["counts"][key] == 1
    assert result["full_regression_gate"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("field", rc.COMPARABILITY_FIELDS)
def test_different_or_missing_runtime_prevents_attribution(field):
    other = manifest()
    other.pop(field)
    result = rc.compare({}, {}, manifest(), other)
    assert result["status"] == "BLOCKED_INCOMPARABLE"
    assert result["different_or_missing_fields"] == [field]


def test_junit_keeps_collection_errors_and_skip_reason(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text('<testsuite><testcase classname="t" name="ok"/>'
        '<testcase classname="t" name="missing"><error message="import missing">trace</error></testcase>'
        '<testcase classname="t" name="model"><skipped message="no weights"/></testcase></testsuite>')
    result = rc.read_junit(path)
    assert result["t::missing"]["status"] == "error"
    assert result["t::model"]["skip_reason"] == "no weights"


@pytest.mark.parametrize("xml", ['<testsuite/>',
    '<testsuite><testcase name="same"/><testcase name="same"/></testsuite>',
    '<testsuite><testcase name="a"><skipped/><failure/></testcase></testsuite>',
    '<testsuite><error/><testcase name="ok"/></testsuite>'])
def test_incomplete_or_ambiguous_junit_is_rejected(tmp_path, xml):
    path = tmp_path / "report.xml"
    path.write_text(xml)
    with pytest.raises(ValueError): rc.read_junit(path)
