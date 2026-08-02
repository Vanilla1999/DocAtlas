from docmancer.docs.documentation_evidence import assess_documentation_evidence


def test_official_exact_registry_binding_is_accepted() -> None:
    report = assess_documentation_evidence(
        library="github.com/gin-gonic/gin",
        ecosystem="go",
        docs_url="https://pkg.go.dev/github.com/gin-gonic/gin@v1.10.0",
        authority="official_registry",
        requested_version="v1.10.0",
        version_binding="exact",
        version_source="vendor_modules_exact",
    )

    assert report.decision == "accept"
    assert report.identity.status == "confirmed"
    assert report.authority.status == "confirmed"
    assert report.version.status == "confirmed"


def test_external_docs_with_exact_version_still_require_authority_confirmation() -> None:
    report = assess_documentation_evidence(
        library="fastapi",
        ecosystem="python",
        docs_url="https://fastapi.tiangolo.com/",
        authority=None,
        requested_version="0.115.6",
        version_binding="exact",
        version_source="uv.lock_exact",
        discovered_from="pypi_project_metadata",
    )

    assert report.decision == "confirm"
    assert report.identity.status == "confirmed"
    assert report.version.status == "confirmed"
    assert "source authority has not been established" in report.reasons


def test_unsafe_url_is_rejected_even_when_other_claims_look_exact() -> None:
    report = assess_documentation_evidence(
        library="sample",
        ecosystem="python",
        docs_url="http://docs.example/sample/1.0",
        authority="official_project",
        requested_version="1.0",
        version_binding="exact",
    )

    assert report.decision == "reject"
    assert report.identity.status == "rejected"


def test_official_registry_claim_is_rejected_on_wrong_origin() -> None:
    report = assess_documentation_evidence(
        library="github.com/gin-gonic/gin",
        ecosystem="go",
        docs_url="https://docs.attacker.example/gin/v1.10.0",
        authority="official_registry",
        requested_version="v1.10.0",
        version_binding="exact",
    )

    assert report.decision == "reject"
    assert report.authority.status == "rejected"
