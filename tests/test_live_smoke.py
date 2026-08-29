from datetime import UTC, datetime

import pytest

from vendorproof.models import (
    AuditReport,
    ClaimAssessment,
    ClaimCandidate,
    ClaimResult,
    SourceRecord,
    Verdict,
)
from vendorproof.smoke import validate_live_report


def report(*, with_source: bool, search_error: str | None = None) -> AuditReport:
    candidate = ClaimCandidate(text="Acme supports SSO", query="Acme SSO")
    sources = (
        [
            SourceRecord(
                title="Acme docs",
                url="https://example.com/acme",
                engine="google_light",
                rank=1,
                observed_at=datetime.now(UTC),
            )
        ]
        if with_source
        else []
    )
    return AuditReport(
        generated_at=datetime.now(UTC),
        overall_action="review",
        claims=[
            ClaimResult(
                candidate=candidate,
                sources=sources,
                assessment=ClaimAssessment(
                    claim=candidate.text,
                    verdict=Verdict.INSUFFICIENT,
                    confidence=0,
                    explanation="Needs review.",
                    recommendation="Check the vendor.",
                    citation_urls=[],
                ),
                search_error=search_error,
            )
        ],
    )


def test_live_smoke_requires_claims_and_evidence() -> None:
    empty = AuditReport(
        generated_at=datetime.now(UTC), overall_action="review", claims=[]
    )
    with pytest.raises(SystemExit, match="no claims"):
        validate_live_report(empty)
    with pytest.raises(SystemExit, match="no complete evidence run"):
        validate_live_report(report(with_source=False))
    with pytest.raises(SystemExit, match="no complete evidence run"):
        validate_live_report(
            report(with_source=True, search_error="Partial search failure")
        )


def test_live_smoke_accepts_a_complete_evidence_run() -> None:
    validate_live_report(report(with_source=True))


def test_live_smoke_rejects_sources_from_only_partial_claim() -> None:
    partial = report(with_source=True, search_error="Partial search failure")
    empty_complete = report(with_source=False)
    mixed = partial.model_copy(
        update={"claims": [partial.claims[0], empty_complete.claims[0]]}
    )

    with pytest.raises(SystemExit, match="no complete evidence run"):
        validate_live_report(mixed)
