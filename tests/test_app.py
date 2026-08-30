from datetime import UTC, datetime

import pytest

from vendorproof.app import _service_from_environment, create_app
from vendorproof.models import (
    AuditReport,
    ClaimAssessment,
    ClaimCandidate,
    ClaimResult,
    Verdict,
)
from vendorproof.service import InputError


class FakeService:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.briefs: list[str] = []

    def audit(self, brief: str) -> AuditReport:
        self.briefs.append(brief)
        if self.fail:
            raise self.fail
        candidate = ClaimCandidate(
            entity_anchor="Acme",
            entity_domain="acme.com",
            requirement_anchor="SSO",
            fact_category="other_capability",
            text="Acme supports SSO",
            query="Acme SSO",
        )
        return AuditReport(
            generated_at=datetime.now(UTC),
            overall_action="review",
            claims=[
                ClaimResult(
                    candidate=candidate,
                    assessment=ClaimAssessment(
                        claim=candidate.text,
                        verdict=Verdict.INSUFFICIENT,
                        confidence=0.4,
                        explanation="The current evidence is incomplete.",
                        recommendation="Confirm with the vendor.",
                        citation_urls=[],
                    ),
                )
            ],
        )


def test_home_and_health_render() -> None:
    app = create_app(lambda: FakeService())
    client = app.test_client()

    home = client.get("/")
    health = client.get("/health")

    assert home.status_code == 200
    assert b"Evidence before" in home.data
    assert health.json == {"service": "vendorproof", "status": "ok"}


def test_runtime_factory_allows_local_mode_without_xano(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.delenv("XANO_SNAPSHOT_ENDPOINT", raising=False)
    monkeypatch.delenv("XANO_API_TOKEN", raising=False)
    monkeypatch.setattr("vendorproof.app.create_gemini_client", lambda: object())

    service = _service_from_environment()

    assert service._store is None


def test_runtime_factory_requires_token_for_configured_xano(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.setenv("XANO_SNAPSHOT_ENDPOINT", "https://example.xano.io/snapshots")
    monkeypatch.delenv("XANO_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="XANO_API_TOKEN"):
        _service_from_environment()


def test_analyze_renders_report_and_escapes_input() -> None:
    service = FakeService()
    app = create_app(lambda: service)
    client = app.test_client()

    response = client.post("/analyze", data={"brief": "<script>alert(1)</script>"})

    assert response.status_code == 200
    assert service.briefs == ["<script>alert(1)</script>"]
    assert b"Decision state" in response.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data
    assert b"<script>alert(1)</script>" not in response.data


def test_analyze_shows_safe_validation_and_provider_errors() -> None:
    invalid = create_app(lambda: FakeService(fail=InputError("Add more detail.")))
    unavailable = create_app(lambda: FakeService(fail=RuntimeError("secret")))

    invalid_response = invalid.test_client().post("/analyze", data={"brief": "x"})
    unavailable_response = unavailable.test_client().post(
        "/analyze", data={"brief": "valid brief"}
    )

    assert invalid_response.status_code == 400
    assert b"Add more detail." in invalid_response.data
    assert unavailable_response.status_code == 503
    assert b"temporarily unavailable" in unavailable_response.data
    assert b"secret" not in unavailable_response.data


def test_reviewer_code_is_enforced(monkeypatch) -> None:
    monkeypatch.setenv("REVIEWER_ACCESS_CODE", "correct-code")
    service = FakeService()
    app = create_app(lambda: service)
    client = app.test_client()

    denied = client.post(
        "/analyze", data={"brief": "valid brief", "access_code": "wrong"}
    )
    allowed = client.post(
        "/analyze", data={"brief": "valid brief", "access_code": "correct-code"}
    )

    assert denied.status_code == 403
    assert service.briefs == ["valid brief"]
    assert allowed.status_code == 200


def test_multibyte_brief_reaches_character_validation() -> None:
    service = FakeService()
    app = create_app(lambda: service)

    response = app.test_client().post("/analyze", data={"brief": "测" * 12_000})

    assert response.status_code == 200
    assert service.briefs == ["测" * 12_000]


def test_extraction_warning_is_visible() -> None:
    class WarningService(FakeService):
        def audit(self, brief: str) -> AuditReport:
            report = super().audit(brief)
            return report.model_copy(
                update={"extraction_warning": "One generated check was excluded."}
            )

    response = create_app(lambda: WarningService()).test_client().post(
        "/analyze", data={"brief": "Compare Acme."}
    )

    assert response.status_code == 200
    assert b"One generated check was excluded." in response.data
