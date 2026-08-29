from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from vendorproof.models import (
    MAX_EXPLANATION_CHARS,
    MAX_RECOMMENDATION_CHARS,
    AuditReport,
    ClaimAssessment,
    ClaimCandidate,
    ClaimResult,
    SearchOutcome,
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
    def search(self, query: str) -> SearchOutcome: ...


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
            outcome = self._searcher.search(candidate.query)
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

        assessment = self._judge.assess(candidate, outcome.sources)
        guarded = self._enforce_citation_provenance(assessment, outcome.sources)
        search_error = None
        if outcome.failed_engines:
            failed = ", ".join(outcome.failed_engines)
            if guarded.verdict in {Verdict.CHANGED, Verdict.CONFLICTING}:
                explanation_suffix = (
                    f" Evidence is partial because {failed} failed during this run."
                )
                recommendation_suffix = (
                    " Also retry the missing evidence channel."
                )
                guarded = guarded.model_copy(
                    update={
                        "explanation": self._append_bounded(
                            guarded.explanation,
                            explanation_suffix,
                            MAX_EXPLANATION_CHARS,
                        ),
                        "recommendation": self._append_bounded(
                            guarded.recommendation,
                            recommendation_suffix,
                            MAX_RECOMMENDATION_CHARS,
                        ),
                    }
                )
            else:
                guarded = guarded.model_copy(
                    update={
                        "verdict": Verdict.INSUFFICIENT,
                        "confidence": min(guarded.confidence, 0.5),
                        "explanation": (
                            "Only partial live evidence was available because "
                            f"{failed} failed during this run."
                        ),
                        "recommendation": (
                            "Retry the missing evidence channel before shortlisting."
                        ),
                    }
                )
            search_error = f"Partial search failure: {failed}."
        return ClaimResult(
            candidate=candidate,
            sources=outcome.sources,
            assessment=guarded,
            search_error=search_error,
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
    def _append_bounded(text: str, suffix: str, max_chars: int) -> str:
        if len(text) + len(suffix) <= max_chars:
            return text + suffix
        prefix = text[: max_chars - len(suffix)].rstrip()
        return prefix + suffix

    @staticmethod
    def _overall_action(results: list[ClaimResult]) -> str:
        if not results:
            return "review"
        verdicts = {result.assessment.verdict for result in results}
        if verdicts & {Verdict.CHANGED, Verdict.CONFLICTING}:
            return "hold"
        if Verdict.INSUFFICIENT in verdicts:
            return "review"
        return "publish"
