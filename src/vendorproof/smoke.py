from vendorproof.models import AuditReport


def validate_live_report(report: AuditReport) -> None:
    if not report.claims:
        raise SystemExit("Live smoke failed: Gemini extracted no claims.")
    complete_with_evidence = any(
        not result.search_error and result.sources for result in report.claims
    )
    if not complete_with_evidence:
        raise SystemExit(
            "Live smoke failed: SerpApi returned no complete evidence run."
        )
