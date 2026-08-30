# VendorProof project rules

VendorProof is a standalone entry for the DevNetwork [API + Cloud + AI]
Hackathon 2026. It must remain isolated from the submitted Agentic Brief and
ScriptProof repositories.

## Current release state

- Production window: 2026-08-29 through 2026-08-30, two focused calendar days
  from product selection to a positively confirmed Devpost submission.
- Devpost: `https://devpost.com/software/vendorproof` (`SUBMITTED`, project
  `1160958`).
- Production: `https://vendorproof-web-qjv2kumm3q-as.a.run.app/`, Cloud Run
  revision `vendorproof-web-00003-qeg` at 100% traffic.
- Public demo: `https://youtu.be/z9RUGx1DMT8` (3:15, public).
- Release code: `3aac90d`; submission record: `004c116`; final recorded CI run:
  `33302070873` (passed).
- Verification: 391 tests, 95.26% branch-aware coverage, Ruff and Gitleaks clean,
  with independent review converged.
- Post-submission closeout recheck: the home and health routes remained HTTP
  200, and two live analyses returned real cited dossiers. Both current runs
  skipped Xano persistence because the official-domain identity guard could not
  confirm every vendor from that run's search evidence. This is an honestly
  surfaced degraded-persistence state, not a new full-chain acceptance and not
  evidence that the earlier accepted production snapshot `48` disappeared.
- Status: submitted and frozen until judging ends. Do not change the repository,
  production service, video, or Devpost materials except for a confirmed
  availability or security incident. Any incident change must repeat the full
  release and submission verification gates in `NEXT.md`.

## Competition gates

- Deadline: 2026-09-04 01:00 Asia/Singapore.
- Sponsor tracks: SerpApi — Best AI Use Case; Xano: Rebuild a SaaS Tool You Hate.
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
