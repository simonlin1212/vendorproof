from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    HttpUrl,
    TypeAdapter,
    WithJsonSchema,
    field_validator,
)

HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)
MAX_EXPLANATION_CHARS = 2_000
MAX_RECOMMENDATION_CHARS = 1_000


def validate_public_url(value: str) -> str:
    raw = str(value)
    has_control = any(
        ord(character) < 32 or ord(character) == 127 for character in raw
    )
    if raw != raw.strip() or has_control:
        raise ValueError(
            "URL must not contain whitespace controls or surrounding space."
        )
    try:
        HTTP_URL_ADAPTER.validate_python(raw)
    except ValueError as exc:
        raise ValueError("URL must be a valid public HTTP or HTTPS URL.") from exc
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be a public HTTP or HTTPS URL.")
    return raw


PublicHttpUrl = Annotated[
    str,
    Field(min_length=8, max_length=2_000),
    AfterValidator(validate_public_url),
    WithJsonSchema(
        {
            "type": "string",
            "format": "uri",
            "minLength": 8,
            "maxLength": 2_000,
        }
    ),
]


class Verdict(StrEnum):
    SUPPORTED = "supported"
    CHANGED = "changed"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


class ClaimCandidate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    query: str = Field(min_length=3, max_length=300)
    why_check: str = Field(default="Time-sensitive external claim.", max_length=500)
    priority: int = Field(default=3, ge=1, le=5)

    @field_validator("text", "query", "why_check")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class SourceRecord(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    url: PublicHttpUrl
    snippet: str = Field(default="", max_length=2_000)
    source: str = Field(default="", max_length=200)
    published_at: str | None = Field(default=None, max_length=100)
    engine: Literal["google_light", "google_news"]
    rank: int = Field(ge=1, le=100)
    observed_at: datetime
    search_id: str | None = Field(default=None, max_length=100)

class SearchOutcome(BaseModel):
    sources: list[SourceRecord] = Field(default_factory=list, max_length=20)
    failed_engines: list[Literal["google_light", "google_news"]] = Field(
        default_factory=list, max_length=2
    )


class ClaimBatch(BaseModel):
    claims: list[ClaimCandidate] = Field(default_factory=list, max_length=8)


class ClaimAssessment(BaseModel):
    claim: str = Field(min_length=1, max_length=500)
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=MAX_EXPLANATION_CHARS)
    recommendation: str = Field(min_length=1, max_length=MAX_RECOMMENDATION_CHARS)
    citation_urls: list[PublicHttpUrl] = Field(default_factory=list, max_length=10)


class ClaimResult(BaseModel):
    candidate: ClaimCandidate
    sources: list[SourceRecord] = Field(default_factory=list, max_length=20)
    assessment: ClaimAssessment
    search_error: str | None = None


class SnapshotReceipt(BaseModel):
    snapshot_id: str = Field(min_length=1, max_length=100)
    previous_snapshot_id: str | None = Field(default=None, max_length=100)
    changed_claims: int = Field(default=0, ge=0, le=100)


class AuditReport(BaseModel):
    generated_at: datetime
    overall_action: Literal["publish", "review", "hold"]
    claims: list[ClaimResult]
    snapshot: SnapshotReceipt | None = None
    persistence_error: str | None = None
