from datetime import datetime, timezone

from docmancer.docs.domain.policies import docs_policy, is_stale


def test_is_stale_treats_missing_and_invalid_as_stale():
    now = datetime(2024, 1, 10, tzinfo=timezone.utc)

    assert is_stale(None, stale_after_days=30, now=now) is True
    assert is_stale("not-a-date", stale_after_days=30, now=now) is True


def test_is_stale_preserves_boundary_behavior():
    now = datetime(2024, 1, 31, tzinfo=timezone.utc)

    assert is_stale("2024-01-01T00:00:00+00:00", stale_after_days=30, now=now) is True
    assert is_stale("2024-01-02T00:00:00+00:00", stale_after_days=30, now=now) is False
    assert is_stale("2024-01-01T00:00:00", stale_after_days=30, now=now) is True


def test_docs_policy_preserves_direct_webfetch_decisions():
    assert docs_policy("ambiguous", has_registered_source=True) == {
        "direct_webfetch": "forbidden",
        "reason_code": "registry_candidates_exist",
    }
    assert docs_policy("success", has_registered_source=True) == {
        "direct_webfetch": "forbidden",
        "reason_code": "registered_source_exists",
    }
    assert docs_policy("needs_input", has_registered_source=False) == {
        "direct_webfetch": "discovery_only",
        "reason_code": "no_registered_source",
    }
