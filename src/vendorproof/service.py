from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from vendorproof.models import (
    AuditReport,
    ClaimAssessment,
    ClaimCandidate,
    ClaimResult,
    SnapshotReceipt,
    SourceRecord,
    Verdict,
)

MAX_INPUT_CHARS = 12_000
MAX_CLAIMS = 5


class InputError(ValueError):
    """The submitted text cannot be audited safely."""


class ClaimExtractor(Protocol):
    def extract(self, text: str) -> list[ClaimCandidate]: ...


class LiveSearcher(Protocol):
    def search(self, query: str) -> list[SourceRecord]: ...


class EvidenceJudge(Protocol):
    def assess(
        self, claim: ClaimCandidate, sources: list[SourceRecord]
    ) -> ClaimAssessment: ...


class AuditStore(Protocol):
    def save(self, brief: str, report: AuditReport) -> SnapshotReceipt: ...


class AuditService:
    def __init__(
        self,
        extractor: ClaimExtractor,
        searcher: LiveSearcher,
        judge: EvidenceJudge,
        store: AuditStore | None = None,
    ) -> None:
        self._extractor = extractor
        self._searcher = searcher
        self._judge = judge
        self._store = store

    def audit(self, text: str) -> AuditReport:
        normalized = self._normalize_input(text)
        candidates = self._bounded_unique_claims(self._extractor.extract(normalized))
        results = [self._audit_claim(candidate) for candidate in candidates]
        report = AuditReport(
            generated_at=datetime.now(UTC),
            overall_action=self._overall_action(results),
            claims=results,
        )
        if self._store is None:
            return report
        try:
            receipt = self._store.save(normalized, report)
        except Exception:
            return report.model_copy(
                update={
                    "persistence_error": (
                        "The evidence file was generated, but Xano history could "
                        "not be saved."
                    )
                }
            )
        return report.model_copy(update={"snapshot": receipt})

    @staticmethod
    def _normalize_input(text: str) -> str:
        normalized = text.strip().replace("\r\n", "\n").replace("\r", "\n")
        if not normalized:
            raise InputError("Paste at least one sentence to audit.")
        if len(normalized) > MAX_INPUT_CHARS:
            raise InputError(f"Input must be {MAX_INPUT_CHARS:,} characters or fewer.")
        return normalized

    @staticmethod
    def _bounded_unique_claims(
        candidates: list[ClaimCandidate],
    ) -> list[ClaimCandidate]:
        unique: list[ClaimCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.text.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
            if len(unique) == MAX_CLAIMS:
                break
        return unique

    def _audit_claim(self, candidate: ClaimCandidate) -> ClaimResult:
        try:
            sources = self._searcher.search(candidate.query)
        except Exception:
            return ClaimResult(
                candidate=candidate,
                sources=[],
                assessment=ClaimAssessment(
                    claim=candidate.text,
                    verdict=Verdict.INSUFFICIENT,
                    confidence=0,
                    explanation=(
                        "Live search failed, so VendorProof cannot issue a current "
                        "evidence verdict."
                    ),
                    recommendation="Retry the live search before publishing.",
                    citation_urls=[],
                ),
                search_error="Live search was unavailable for this claim.",
            )

        assessment = self._judge.assess(candidate, sources)
        guarded = self._enforce_citation_provenance(assessment, sources)
        return ClaimResult(
            candidate=candidate,
            sources=sources,
            assessment=guarded,
        )

    @staticmethod
    def _enforce_citation_provenance(
        assessment: ClaimAssessment, sources: list[SourceRecord]
    ) -> ClaimAssessment:
        observed = {str(source.url) for source in sources}
        citations = [
            citation
            for citation in assessment.citation_urls
            if str(citation) in observed
        ]
        updates: dict[str, object] = {"citation_urls": citations}
        if assessment.verdict != Verdict.INSUFFICIENT and not citations:
            updates.update(
                verdict=Verdict.INSUFFICIENT,
                confidence=0,
                explanation=(
                    "The model returned no citation observed in the current "
                    "SerpApi results, so the verdict was downgraded."
                ),
                recommendation="Review current sources manually before publishing.",
            )
        return assessment.model_copy(update=updates)

    @staticmethod
    def _overall_action(results: list[ClaimResult]) -> str:
        verdicts = {result.assessment.verdict for result in results}
        if verdicts & {Verdict.CHANGED, Verdict.CONFLICTING}:
            return "hold"
        if Verdict.INSUFFICIENT in verdicts:
            return "review"
        return "publish"
