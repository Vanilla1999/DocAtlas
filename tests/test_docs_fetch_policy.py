from __future__ import annotations

import ipaddress

import pytest

from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError


PUBLIC = ipaddress.ip_address("93.184.216.34")


def _resolver(*answers: str):
    resolved = tuple(ipaddress.ip_address(value) for value in answers)
    return lambda _host: resolved


@pytest.mark.parametrize(
    ("url", "category"),
    [
        ("https://127.0.0.1/docs", "private_network_blocked"),
        ("https://[::1]/docs", "private_network_blocked"),
        ("https://169.254.169.254/latest/meta-data", "private_network_blocked"),
        ("https://[::ffff:127.0.0.1]/docs", "private_network_blocked"),
    ],
)
def test_policy_rejects_private_and_metadata_targets(url: str, category: str):
    policy = DocsFetchPolicy(resolver=lambda host: (ipaddress.ip_address(host),))

    with pytest.raises(DocsFetchSecurityError) as exc:
        policy.validate_url(url)

    assert exc.value.category == category


def test_policy_rejects_hostname_when_any_dns_answer_is_private():
    policy = DocsFetchPolicy(resolver=_resolver("93.184.216.34", "10.0.0.4"))

    with pytest.raises(DocsFetchSecurityError) as exc:
        policy.validate_url("https://example.com/docs")

    assert exc.value.category == "private_network_blocked"


def test_policy_rejects_unresolved_hostname():
    policy = DocsFetchPolicy(resolver=lambda _host: ())

    with pytest.raises(DocsFetchSecurityError) as exc:
        policy.validate_url("https://example.com/docs")

    assert exc.value.category == "host_resolution_failed"


def test_policy_converts_resolver_failure_to_typed_safe_error():
    def failing_resolver(_host: str):
        raise OSError("resolver detail must not escape")

    with pytest.raises(DocsFetchSecurityError) as exc:
        DocsFetchPolicy(resolver=failing_resolver).validate_url("https://example.com/docs")

    assert exc.value.category == "host_resolution_failed"
    assert "resolver detail" not in str(exc.value)


def test_policy_enforces_allowed_hosts_and_path_prefixes():
    policy = DocsFetchPolicy(
        resolver=_resolver(str(PUBLIC)),
        allowed_hosts=("docs.example.com",),
        path_prefixes=("/guide",),
    )

    assert policy.validate_url("https://docs.example.com/guide/start").host == "docs.example.com"
    with pytest.raises(DocsFetchSecurityError, match="host_not_allowed"):
        policy.validate_url("https://other.example.com/guide/start")
    with pytest.raises(DocsFetchSecurityError, match="path_not_allowed"):
        policy.validate_url("https://docs.example.com/admin")


def test_scope_probe_does_not_resolve_and_rejects_origin_robots_outside_path():
    calls = []
    policy = DocsFetchPolicy(
        resolver=lambda host: calls.append(host) or (ipaddress.ip_address(str(PUBLIC)),),
        allowed_hosts=("docs.example.com",),
        path_prefixes=("/docs",),
    )

    assert policy.allows_scope("https://docs.example.com/docs/sitemap.xml") is True
    assert policy.allows_scope("https://docs.example.com/robots.txt") is False
    assert calls == []


def test_allowed_domain_includes_its_subdomains_but_not_suffix_confusion():
    policy = DocsFetchPolicy(
        resolver=_resolver(str(PUBLIC)),
        allowed_hosts=("example.com",),
    )

    assert policy.validate_url("https://docs.example.com/guide").host == "docs.example.com"
    with pytest.raises(DocsFetchSecurityError, match="host_not_allowed"):
        policy.validate_url("https://example.com.evil.test/guide")


def test_policy_rejects_invalid_port_without_resolving():
    called = False

    def resolver(_host: str):
        nonlocal called
        called = True
        return (PUBLIC,)

    with pytest.raises(DocsFetchSecurityError, match="invalid_url") as exc:
        DocsFetchPolicy(resolver=resolver).validate_url("https://example.com:not-a-port/docs")

    assert called is False
    assert exc.value.__cause__ is None


def test_userinfo_error_redacts_credentials():
    policy = DocsFetchPolicy(resolver=_resolver(str(PUBLIC)))

    with pytest.raises(DocsFetchSecurityError) as exc:
        policy.validate_url("https://user:secret@example.com/docs?token=also-secret")

    assert exc.value.category == "userinfo_not_allowed"
    assert "secret" not in str(exc.value)
    assert "secret" not in exc.value.redacted_url
