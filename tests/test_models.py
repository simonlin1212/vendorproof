from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vendorproof.models import ClaimAssessment, ClaimCandidate, SourceRecord, Verdict


def test_claim_candidate_rejects_empty_or_oversized_text() -> None:
    with pytest.raises(ValidationError):
        ClaimCandidate(text="", query="current status")

    with pytest.raises(ValidationError):
        ClaimCandidate(text="x" * 501, query="current status")


def test_source_record_requires_public_http_url() -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            title="Local file",
            url="file:///tmp/source",
            snippet="not public",
            engine="google_light",
            rank=1,
            observed_at=datetime.now(UTC),
        )


def test_source_and_citation_urls_preserve_provider_bytes() -> None:
    raw_url = "https://EXAMPLE.com/%7Evendor?Plan=Pro"
    source = SourceRecord(
        title="Pricing",
        url=raw_url,
        engine="google_light",
        rank=1,
        observed_at=datetime.now(UTC),
    )
    assessment = ClaimAssessment(
        claim="The plan exists.",
        verdict=Verdict.SUPPORTED,
        confidence=0.8,
        explanation="Observed in current results.",
        recommendation="Review pricing details.",
        citation_urls=[raw_url],
    )

    assert source.url == raw_url
    assert assessment.citation_urls == [raw_url]


def test_citation_schema_keeps_uri_constraint_for_structured_output() -> None:
    schema = ClaimAssessment.model_json_schema()
    citation_schema = schema["properties"]["citation_urls"]["items"]

    assert citation_schema["format"] == "uri"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com\n@evil.com",
        "https://example.com\t@evil.com",
        "https://example.com/\x01path",
        " https://example.com/path",
    ],
)
def test_source_and_citation_urls_reject_controls_and_surrounding_space(
    url: str,
) -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            title="Unsafe",
            url=url,
            engine="google_light",
            rank=1,
            observed_at=datetime.now(UTC),
        )

    with pytest.raises(ValidationError):
        ClaimAssessment(
            claim="The plan exists.",
            verdict=Verdict.SUPPORTED,
            confidence=0.8,
            explanation="Observed in current results.",
            recommendation="Review pricing details.",
            citation_urls=[url],
        )


@pytest.mark.parametrize(
    "url", ["https://exa mple.com/path", "https://example.com:bad/path"]
)
def test_source_record_rejects_malformed_http_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            title="Malformed",
            url=url,
            engine="google_light",
            rank=1,
            observed_at=datetime.now(UTC),
        )
