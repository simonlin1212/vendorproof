from __future__ import annotations

import os

from dotenv import load_dotenv

from vendorproof.app import SAMPLE_BRIEF, _service_from_environment
from vendorproof.smoke import validate_live_report


def main() -> None:
    load_dotenv()
    required = ["SERPAPI_API_KEY", "GOOGLE_CLOUD_PROJECT"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing required configuration: {', '.join(missing)}")

    report = _service_from_environment().audit(SAMPLE_BRIEF)
    validate_live_report(report)
    print(
        f"LIVE_SMOKE=ok action={report.overall_action} "
        f"claims={len(report.claims)}"
    )
    for index, result in enumerate(report.claims, start=1):
        print(
            f"{index}. verdict={result.assessment.verdict.value} "
            f"sources={len(result.sources)} "
            f"citations={len(result.assessment.citation_urls)}"
        )
    if report.snapshot:
        print(f"XANO_SNAPSHOT=ok id={report.snapshot.snapshot_id}")
    elif os.getenv("XANO_SNAPSHOT_ENDPOINT"):
        raise SystemExit(report.persistence_error or "Xano snapshot was not saved.")
if __name__ == "__main__":
    main()
