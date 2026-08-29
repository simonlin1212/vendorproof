from datetime import UTC, datetime

import pytest

from vendorproof.models import (
    MAX_EXPLANATION_CHARS,
    MAX_RECOMMENDATION_CHARS,
    ClaimAssessment,
    ClaimCandidate,
    SearchOutcome,
    SnapshotReceipt,
    SourceRecord,
    Verdict,
)
from vendorproof.service import MAX_CLAIMS, AuditService, InputError


class FakeExtractor:
    def __init__(self, claims: list[ClaimCandidate]) -> None:
        self.claims = claims
        self.inputs: list[str] = []

    def extract(self, text: str) -> list[ClaimCandidate]:
        self.inputs.append(text)
        return self.claims


class FakeSearcher:
    def __init__(
        self,
        sources: list[SourceRecord],
        *,
        fail: bool = False,
        failed_engines: list[str] | None = None,
    ) -> None:
        self.sources = sources
        self.fail = fail
        self.failed_engines = failed_engines or []
        self.queries: list[str] = []

    def search(self, query: str) -> SearchOutcome:
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("provider unavailable")
        return SearchOutcome(
            sources=self.sources, failed_engines=self.failed_engines
        )


class FakeJudge:
    def __init__(self, assessment: ClaimAssessment) -> None:
        self.assessment = assessment
        self.calls: list[tuple[ClaimCandidate, list[SourceRecord]]] = []

    def assess(
        self, claim: ClaimCandidate, sources: list[SourceRecord]
    ) -> ClaimAssessment:
        self.calls.append((claim, sources))
        return self.assessment.model_copy(update={"claim": claim.text})


class FakeStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, object]] = []

    def save(self, brief: str, report: object) -> SnapshotReceipt:
        self.calls.append((brief, report))
        if self.fail:
            raise RuntimeError("xano unavailable")
        return SnapshotReceipt(snapshot_id="42", changed_claims=1)


def source(url: str = "https://example.com/current") -> SourceRecord:
    return SourceRecord(
        title="Current source",
        url=url,
        snippet="The current documented status.",
        source="Example",
        published_at="2026-08-29",
        engine="google_news",
        rank=1,
        observed_at=datetime.now(UTC),
    )


def claim(text: str = "Acme launched the product in 2026.") -> ClaimCandidate:
    return ClaimCandidate(
        text=text,
        query="Acme product launch current status",
        why_check="The launch status can change.",
        priority=5,
    )


def assessment(
    *,
    verdict: Verdict = Verdict.SUPPORTED,
    citations: list[str] | None = None,
) -> ClaimAssessment:
    return ClaimAssessment(
        claim="placeholder",
        verdict=verdict,
        confidence=0.9,
        explanation="Current evidence supports the claim.",
        recommendation="Keep the sentence.",
        citation_urls=citations or ["https://example.com/current"],
    )


def test_audit_rejects_empty_and_oversized_input() -> None:
    service = AuditService(
        FakeExtractor([]), FakeSearcher([]), FakeJudge(assessment())
    )

    with pytest.raises(InputError):
        service.audit("   ")

    with pytest.raises(InputError):
        service.audit("x" * 12_001)


def test_audit_normalizes_input_and_skips_search_when_no_claims() -> None:
    extractor = FakeExtractor([])
    searcher = FakeSearcher([])
    judge = FakeJudge(assessment())
    service = AuditService(extractor, searcher, judge)

    report = service.audit("  A short draft.\r\n\r\n  ")

    assert extractor.inputs == ["A short draft."]
    assert searcher.queries == []
    assert judge.calls == []
    assert report.overall_action == "review"
    assert report.claims == []


def test_audit_deduplicates_claims_and_limits_work() -> None:
    duplicate = claim()
    claims = [duplicate, duplicate] + [claim(f"Claim {index}") for index in range(10)]
    searcher = FakeSearcher([source()])
    judge = FakeJudge(assessment())
    service = AuditService(FakeExtractor(claims), searcher, judge)

    report = service.audit("A draft with many claims.")

    assert len(report.claims) == MAX_CLAIMS
    assert len(searcher.queries) == MAX_CLAIMS
    assert len(judge.calls) == MAX_CLAIMS


def test_audit_keeps_only_citations_observed_in_serpapi_results() -> None:
    judge = FakeJudge(
        assessment(
            citations=[
                "https://example.com/current",
                "https://invented.example/not-observed",
            ]
        )
    )
    service = AuditService(FakeExtractor([claim()]), FakeSearcher([source()]), judge)

    report = service.audit("A draft.")

    result = report.claims[0]
    assert [str(url) for url in result.assessment.citation_urls] == [
        "https://example.com/current"
    ]
    assert result.assessment.verdict == Verdict.SUPPORTED


def test_definitive_verdict_without_observed_citation_is_downgraded() -> None:
    judge = FakeJudge(assessment(citations=["https://invented.example/source"]))
    service = AuditService(FakeExtractor([claim()]), FakeSearcher([source()]), judge)

    report = service.audit("A draft.")

    result = report.claims[0].assessment
    assert result.verdict == Verdict.INSUFFICIENT
    assert result.citation_urls == []
    assert report.overall_action == "review"


def test_search_failure_becomes_visible_insufficient_evidence() -> None:
    judge = FakeJudge(assessment())
    service = AuditService(
        FakeExtractor([claim()]), FakeSearcher([], fail=True), judge
    )

    report = service.audit("A draft.")

    result = report.claims[0]
    assert result.assessment.verdict == Verdict.INSUFFICIENT
    assert "search failed" in result.assessment.explanation.lower()
    assert result.search_error == "Live search was unavailable for this claim."
    assert judge.calls == []


def test_partial_search_failure_downgrades_definitive_verdict() -> None:
    service = AuditService(
        FakeExtractor([claim()]),
        FakeSearcher([source()], failed_engines=["google_news"]),
        FakeJudge(assessment()),
    )

    report = service.audit("A procurement brief.")

    result = report.claims[0]
    assert result.assessment.verdict == Verdict.INSUFFICIENT
    assert result.assessment.confidence == 0.5
    assert result.search_error == "Partial search failure: google_news."
    assert report.overall_action == "review"


def test_partial_search_failure_preserves_changed_hold() -> None:
    service = AuditService(
        FakeExtractor([claim()]),
        FakeSearcher([source()], failed_engines=["google_news"]),
        FakeJudge(assessment(verdict=Verdict.CHANGED)),
    )

    report = service.audit("A procurement brief.")

    result = report.claims[0]
    assert result.assessment.verdict == Verdict.CHANGED
    assert "partial" in result.assessment.explanation.lower()
    assert result.search_error == "Partial search failure: google_news."
    assert report.overall_action == "hold"


def test_partial_search_failure_keeps_assessment_within_contract_limits() -> None:
    long_assessment = ClaimAssessment(
        claim="placeholder",
        verdict=Verdict.CONFLICTING,
        confidence=0.9,
        explanation="x" * MAX_EXPLANATION_CHARS,
        recommendation="y" * MAX_RECOMMENDATION_CHARS,
        citation_urls=["https://example.com/current"],
    )
    service = AuditService(
        FakeExtractor([claim()]),
        FakeSearcher([source()], failed_engines=["google_news"]),
        FakeJudge(long_assessment),
    )

    report = service.audit("A procurement brief.")
    result = report.claims[0].assessment

    assert result.verdict == Verdict.CONFLICTING
    assert len(result.explanation) <= MAX_EXPLANATION_CHARS
    assert len(result.recommendation) <= MAX_RECOMMENDATION_CHARS
    assert result.explanation.endswith("failed during this run.")
    assert result.recommendation.endswith("missing evidence channel.")
    assert result == ClaimAssessment.model_validate(result.model_dump())


def test_audit_persists_snapshot_and_surfaces_xano_failure() -> None:
    store = FakeStore()
    service = AuditService(
        FakeExtractor([claim()]),
        FakeSearcher([source()]),
        FakeJudge(assessment()),
        store=store,
    )

    report = service.audit("  A procurement brief.  ")

    assert report.snapshot is not None
    assert report.snapshot.snapshot_id == "42"
    assert store.calls[0][0] == "A procurement brief."

    failed_report = AuditService(
        FakeExtractor([claim()]),
        FakeSearcher([source()]),
        FakeJudge(assessment()),
        store=FakeStore(fail=True),
    ).audit("A procurement brief.")
    assert failed_report.snapshot is None
    assert "Xano history" in failed_report.persistence_error


@pytest.mark.parametrize(
    ("verdict", "expected_action"),
    [
        (Verdict.SUPPORTED, "publish"),
        (Verdict.INSUFFICIENT, "review"),
        (Verdict.CHANGED, "hold"),
        (Verdict.CONFLICTING, "hold"),
    ],
)
def test_overall_action_tracks_highest_claim_risk(
    verdict: Verdict, expected_action: str
) -> None:
    service = AuditService(
        FakeExtractor([claim()]),
        FakeSearcher([source()]),
        FakeJudge(assessment(verdict=verdict)),
    )

    assert service.audit("A draft.").overall_action == expected_action
