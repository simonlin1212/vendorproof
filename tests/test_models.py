from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vendorproof.models import ClaimCandidate, SourceRecord


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
