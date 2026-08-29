# VendorProof project rules

VendorProof is a standalone entry for the DevNetwork [API + Cloud + AI]
Hackathon 2026. It must remain isolated from the submitted Agentic Brief and
ScriptProof repositories.

## Competition gates

- Deadline: 2026-09-04 01:00 Asia/Singapore.
- Sponsor tracks: SerpApi — Best AI Use Case; Xano — Best AI Application.
- SerpApi must be called at runtime for the working demo. Static or fabricated
  search results do not qualify.
- Submission needs a working project page, screenshots, a public repository,
  and a short end-to-end demo video.
- Only explicit cash is counted. Each selected sponsor track awards USD 1,000
  for first place and USD 500 for second place.

## Product boundary

VendorProof replaces procurement-comparison spreadsheets with a live, cited
research workspace. It checks vendor pricing, capabilities, limits, and recent
risk signals. It is not a general chatbot and must not present search snippets
as definitive truth without a visible uncertainty state.

## Engineering rules

- Python 3.12 via `uv`; do not use the system Python 3.9 environment.
- Secrets live only in `.env` or the deployment secret store and are never
  committed.
- Every public citation must exactly match a URL returned by a live SerpApi call.
- Model output is validated with Pydantic before rendering.
- User input is bounded, normalized, and never rendered as trusted HTML.
- External calls are mocked in unit tests; live smoke tests are separate.
- Run Ruff, pytest with coverage, an independent review, and a production smoke
  test before submission.

## Working entrypoints

- `NEXT.md`: current state and exact next action.
- `DEV_LOG.md`: dated implementation and submission evidence.
- `docs/COMPETITION_RULES.md`: verified official requirements.
