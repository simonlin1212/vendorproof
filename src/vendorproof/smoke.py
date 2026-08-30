from vendorproof.models import AuditReport


def validate_live_report(report: AuditReport) -> None:
    if not report.claims:
        raise SystemExit("Live smoke failed: Gemini extracted no claims.")
    if report.extraction_warning:
        raise SystemExit("Live smoke failed: Gemini extraction was incomplete.")
    complete_with_evidence = any(
        not result.search_error
        and result.sources
        and result.entity_domain_verified
        and result.assessment.citation_urls
        for result in report.claims
    )
    if not complete_with_evidence:
        raise SystemExit(
            "Live smoke failed: SerpApi returned no complete evidence run."
        )
    if report.snapshot is None:
        raise SystemExit(
            report.persistence_error
            or "Live smoke failed: Xano returned no snapshot receipt."
        )
