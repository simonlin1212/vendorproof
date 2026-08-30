import runpy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vendorproof.models import (
    AuditReport,
    ClaimAssessment,
    ClaimCandidate,
    ClaimResult,
    SnapshotReceipt,
    SourceRecord,
    Verdict,
)
from vendorproof.smoke import validate_live_report


def test_live_script_preflights_xano_and_search_configuration(monkeypatch) -> None:
    script = runpy.run_path(
        str(Path(__file__).parents[1] / "scripts" / "live_smoke.py")
    )
    main = script["main"]
    monkeypatch.setitem(main.__globals__, "load_dotenv", lambda: None)
    for name in (
        "SERPAPI_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "XANO_SNAPSHOT_ENDPOINT",
        "XANO_API_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit) as error:
        main()

    message = str(error.value)
    assert "SERPAPI_API_KEY" in message
    assert "GOOGLE_CLOUD_PROJECT" in message
    assert "XANO_SNAPSHOT_ENDPOINT" in message
    assert "XANO_API_TOKEN" in message


def report(
    *,
    with_source: bool,
    search_error: str | None = None,
    with_citation: bool = True,
    with_snapshot: bool = True,
) -> AuditReport:
    candidate = ClaimCandidate(
        entity_anchor="Acme",
        entity_domain="acme.com",
        requirement_anchor="SSO",
        fact_category="other_capability",
        text="Acme supports SSO",
        query="Acme SSO",
    )
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
                    citation_urls=(
                        ["https://example.com/acme"]
                        if with_source and with_citation
                        else []
                    ),
                ),
                search_error=search_error,
                entity_domain_verified=with_source,
            )
        ],
        snapshot=(
            SnapshotReceipt(snapshot_id="42", changed_claims=1)
            if with_snapshot
            else None
        ),
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


def test_live_smoke_requires_xano_snapshot_receipt() -> None:
    with pytest.raises(SystemExit, match="no snapshot receipt"):
        validate_live_report(report(with_source=True, with_snapshot=False))


def test_live_smoke_rejects_incomplete_extraction() -> None:
    incomplete = report(with_source=True).model_copy(
        update={"extraction_warning": "One generated check was rejected."}
    )

    with pytest.raises(SystemExit, match="extraction was incomplete"):
        validate_live_report(incomplete)


def test_live_smoke_rejects_sources_from_only_partial_claim() -> None:
    partial = report(with_source=True, search_error="Partial search failure")
    empty_complete = report(with_source=False)
    mixed = partial.model_copy(
        update={"claims": [partial.claims[0], empty_complete.claims[0]]}
    )

    with pytest.raises(SystemExit, match="no complete evidence run"):
        validate_live_report(mixed)


def test_live_smoke_rejects_unverified_vendor_identity() -> None:
    unverified = report(with_source=True).model_copy(
        update={
            "claims": [
                report(with_source=True).claims[0].model_copy(
                    update={"entity_domain_verified": False}
                )
            ]
        }
    )

    with pytest.raises(SystemExit, match="no complete evidence run"):
        validate_live_report(unverified)


def test_live_smoke_requires_an_observed_citation() -> None:
    with pytest.raises(SystemExit, match="no complete evidence run"):
        validate_live_report(report(with_source=True, with_citation=False))
