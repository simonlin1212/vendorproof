# VendorProof development log

Updated: 2026-08-29 10:50 Asia/Singapore

## 1. Current status

VendorProof is the active third hackathon project. It is an evidence-first
procurement desk for the DevNetwork [API + Cloud + AI] Hackathon 2026, targeting
the SerpApi and Xano cash tracks.

The codebase, test suite, public repository, Cloud Run preproduction shell,
submission copy, and demo script are complete. The project is **not submitted**
and the public URL is **not yet a working demo**: real SerpApi and Xano accounts,
credentials, and one accepted end-to-end evidence run are still required.

| Area | State | Evidence |
|---|---|---|
| Source repository | Public and clean | `https://github.com/simonlin1212/vendorproof`, `main` at `d5dd5ec` before this log update |
| CI | Passing | GitHub Actions run `33229641295` |
| Unit/regression tests | Passing | 40 tests, 94.37% whole-project coverage |
| Static quality | Passing | Ruff clean |
| Gemini | Verified separately | Vertex AI structured-output smoke passed with `gemini-3.5-flash` in `global` |
| Web UI | Implemented and checked | Desktop/mobile render plus browser functional assertions passed |
| Cloud Run | Preproduction healthy | `vendorproof-web-00001-hzf`; home and health routes return HTTP 200 |
| Real analysis | Gated | `POST /analyze` returns visible HTTP 503 while SerpApi/Xano are unconfigured |
| Devpost registration | Waiting | Browser still requires the user's Devpost account/registration |
| SerpApi account | Waiting | No project credential exists yet |
| Xano workspace | Waiting | No live endpoint/token exists yet |
| Demo video | Script prepared, not recorded | Must use a real successful evidence run |
| Final submission | Not started | Only after the live integration gate passes |

The status words above are deliberate. “Cloud Run is live” means the container,
homepage, and health route work; it does not mean the paid provider integration
or hackathon submission is complete.

## 2. Competition decision

### Event

- Event: DevNetwork [API + Cloud + AI] Hackathon 2026.
- Official online deadline: September 3, 2026 at 10:00 PDT, which is September
  4, 2026 at 01:00 in Singapore/Hong Kong.
- Participation location: Hong Kong.
- Product is being built for cash-award sponsor tracks, not credit-only prizes.

### Track selection

SerpApi and Xano were selected because they can be used in one coherent product:

- SerpApi supplies current Google web and news evidence for decision-critical
  vendor claims.
- Xano stores procurement briefs and evidence snapshots so a later refresh can
  reveal what changed.
- Gemini turns the brief into bounded, verifiable claims and evaluates only the
  returned evidence.

The project will not claim either sponsor track until its real service is called
successfully at runtime and that use is visible in the demo.

## 3. Product definition

Small teams often compare software and suppliers in spreadsheets that go stale
as prices, limitations, integrations, reliability, and security posture change.
General AI answers make the problem worse when they hide uncertainty or cite
pages that were never actually retrieved.

One VendorProof run is designed to:

1. normalize and bound a procurement brief;
2. use Gemini to create at most five decision-critical claims and focused search
   queries;
3. call SerpApi Google Light and Google News searches;
4. evaluate each claim as `supported`, `changed`, `conflicting`, or
   `insufficient`;
5. enforce citation provenance after model output;
6. expose partial provider failures instead of silently treating them as no
   risk;
7. compute a conservative `publish`, `review`, or `hold` decision; and
8. persist the brief and complete evidence snapshot in Xano.

The value proposition is not “AI picks a vendor.” It is “every decision has a
current, inspectable evidence file, including its gaps and contradictions.”

## 4. Architecture and data flow

```text
Browser procurement brief
        |
        v
Cloud Run: Flask orchestrator
        |-- Gemini 3.5 Flash: claim extraction and evidence assessment
        |-- SerpApi: Google Light and Google News
        |-- deterministic evidence/provenance guard
        |-- Xano: brief and immutable report snapshot
        v
Decision dossier: publish / review / hold
```

Only the Flask application and deterministic evidence guard run inside Cloud
Run. Gemini, SerpApi, and Xano are external services. The public README diagram
was corrected to preserve this boundary.

### Main implementation files

| File | Responsibility |
|---|---|
| `src/vendorproof/models.py` | Typed claims, sources, verdicts, reports, limits, and validation |
| `src/vendorproof/providers.py` | Gemini, SerpApi, and Xano provider adapters |
| `src/vendorproof/service.py` | Bounded orchestration, evidence merging, provenance enforcement, risk state |
| `src/vendorproof/app.py` | Flask routes, safe errors, access control, rendering |
| `src/vendorproof/smoke.py` | Real integration acceptance logic |
| `scripts/live_smoke.py` | Operator entry point for the final provider smoke test |
| `docs/XANO_BACKEND.md` | Xano schema, endpoint, authentication, and response contract |
| `docs/DEPLOYMENT.md` | Cloud resources and promotion gate |
| `docs/DEVPOST_SUBMISSION.md` | Copy-ready English Devpost entry |
| `docs/DEMO_SCRIPT.md` | Approximately 2.5-minute English demo plan |

## 5. Evidence and safety invariants

These guarantees are enforced in code, not left only in prompts:

- Procurement briefs are normalized and capped at 12,000 characters.
- A run checks no more than five claims and twenty evidence items per claim.
- Search results are evidence candidates, not automatic truth.
- Public citations must match URLs observed byte-for-byte in the current SerpApi
  response; the model cannot invent or rewrite a source URL.
- Malformed or control-containing URLs are rejected without normalizing away the
  provider's exact citation bytes.
- A definitive verdict without a current observed citation is downgraded.
- Partial web/news failures stay visible and cannot produce a silent all-clear.
- Provider output is validated with Pydantic before rendering or persistence.
- Xano receives the validated complete report snapshot, not a second model
  summary that could drift from the displayed result.
- Credentials remain server-side and are never sent to the browser or committed.
- The production integration fails closed: missing SerpApi/Xano configuration
  yields a visible provider error, never fabricated sample evidence.

## 6. Research and reference work

Before implementation, the project reviewed the official SerpApi Python SDK,
the sponsor's `serpapi-search-tools` reference implementation, current Xano
integration expectations, and the official Devpost event/track requirements.
The external services were kept behind small adapters so their response shapes
and failures could be tested without weakening the real-runtime requirement.

The decision to build a single procurement product across two tracks was made
to avoid two unrelated rushed demos. Track-specific runtime proof is still
required for both sponsors.

## 7. Verification and independent review

### Automated verification

- 40 tests pass.
- Whole-project coverage is 94.37%, including branches.
- Ruff reports no findings.
- GitHub Actions installs the locked environment, runs Ruff, and runs the full
  coverage suite on every push.
- The current public CI head before this administrative update is successful:
  run `33229641295` at `d5dd5ec`.

Coverage includes input bounds, provider parsing, exact citation provenance,
unknown and malformed URLs, partial search failures, verdict downgrades, Xano
persistence behavior, access control, HTML escaping, visible provider errors,
and live-smoke acceptance/failure conditions.

### Review convergence

Five independent finding rounds and a final clean re-review were completed.
Six initial evidence-safety/deployment findings and seven follow-up boundary
regressions were fixed and covered by tests. The final review reported no
actionable regressions.

The fixes included citation-byte preservation, fail-closed provider behavior,
partial-channel risk handling, safe model/provider error surfaces, strict live
smoke criteria, and deployment/documentation consistency.

### Browser and visual QA

The interface was tested for the product promise, procurement form, safety copy,
health endpoint, sample brief, and visible provider failure. Desktop and mobile
layouts were visually inspected, and horizontal overflow was checked. Verified
screenshots are stored under `assets/screenshots/`.

## 8. Public repository and cloud preproduction

### GitHub

- Repository: `https://github.com/simonlin1212/vendorproof`
- Default branch: `main`
- License: MIT
- Public documentation: English plus Simplified Chinese
- CI workflow uses immutable action references.

### Google Cloud

- Project: `our-episode-506708-k6`
- Region: `asia-southeast1`
- Model region: `global`
- Model: `gemini-3.5-flash`
- Service: `vendorproof-web`
- URL: `https://vendorproof-web-qjv2kumm3q-as.a.run.app`
- Latest ready revision: `vendorproof-web-00001-hzf`
- Runtime identity:
  `vendorproof-runtime@our-episode-506708-k6.iam.gserviceaccount.com`
- Runtime permission: Vertex AI user only
- Scaling: maximum two instances and scale-to-zero enabled

### 2026-08-29 10:50 SGT live check

- Cloud Run still reports revision `vendorproof-web-00001-hzf` as ready.
- `GET /health` returned HTTP 200 with
  `{"service":"vendorproof","status":"ok"}`.
- `POST /analyze` returned HTTP 503 because no SerpApi secret is configured.
- This is the required fail-closed behavior, but it is also proof that the URL
  is not yet acceptable as the Devpost working demo.

The dedicated VendorProof service account and service are separate from Agentic
Brief and ScriptProof. No judged artifact from either submitted project was
modified to create VendorProof.

## 9. Submission package prepared

The following materials exist but are not yet final submission evidence:

- copy-ready Devpost project story in `docs/DEVPOST_SUBMISSION.md`;
- approximately 2.5-minute English demo script in `docs/DEMO_SCRIPT.md`;
- architecture and deployment documentation;
- public English and Chinese READMEs;
- current interface and Cloud Run screenshots.

The final evidence dossier screenshot and demo video must be recorded after a
real SerpApi + Xano run. A sample or stub report must never be presented as live
sponsor integration.

## 10. Development timeline

### 2026-08-29 — project start and track selection

Created a standalone repository at
`/Users/simon/Documents/1-Projects/36、VendorProof`. Selected SerpApi and Xano
cash tracks and fixed the product direction as an evidence-first vendor/software
procurement desk.

### 2026-08-29 — implementation

Implemented typed domain models, Gemini claim extraction/assessment, SerpApi
web/news research, exact citation provenance, conservative risk aggregation,
Xano snapshot persistence, Flask UI/API routes, safe failure handling, and a
live integration smoke test.

### 2026-08-29 — verification and public release foundation

Converged the automated suite to 40 tests and 94.37% coverage, completed the
independent review loop, verified the interface in a browser, created the public
GitHub repository, and added passing CI.

### 2026-08-29 — preproduction deployment

Created a dedicated runtime identity and deployed Cloud Run revision
`vendorproof-web-00001-hzf`. Verified the public home and health routes and the
intentional HTTP 503 on unconfigured analysis. Updated public architecture copy
to distinguish the Cloud Run application from external Gemini, SerpApi, and
Xano services.

### 2026-08-29 — account blocker confirmed

Devpost, SerpApi, and Xano were each opened to the correct registration/login
surface, but no authenticated account/workspace was completed. No matching
SerpApi or Xano credentials exist in the local environment or project. Repeated
checks reached the same human-account boundary, so the active project goal was
correctly marked blocked rather than claiming false completion.

## 11. Exact resume and promotion checklist

When Simon is ready, resume in this order:

1. Complete Devpost registration for the DevNetwork event.
2. Create/log into SerpApi and obtain the hackathon-capable key.
3. Create/log into Xano, confirm a zero-cost workspace, and provision the schema
   and server-side snapshot endpoint from `docs/XANO_BACKEND.md`.
4. Store SerpApi and Xano values in Google Secret Manager; grant access only to
   the VendorProof runtime identity.
5. Deploy a tagged or zero-traffic candidate revision pinned to explicit secret
   versions.
6. Run `scripts/live_smoke.py` against Gemini, SerpApi, and Xano.
7. Submit the sample procurement brief through the candidate/public interface.
8. Verify exact clickable SerpApi citations, partial-failure markers, conservative
   verdicts, and a real Xano snapshot receipt.
9. Promote the verified revision to 100% traffic.
10. Capture the real report screenshots and record the demo video.
11. Complete Devpost fields, select both cash tracks, and submit.
12. Re-open the management page and record positive evidence that the entry is
    `SUBMITTED`.

No fake provider, seeded citation, stub result, or fallback report may be used
to bypass steps 4–8.

## 12. Project boundaries and source of truth

- Agentic Brief and ScriptProof are already submitted and frozen. VendorProof
  must remain an independent repository, Cloud Run service, identity, secrets,
  Devpost project, and development log.
- `.env` and credentials must never be committed or printed in logs.
- Do not label the current Cloud Run URL “production demo” until the promotion
  checklist passes.
- Do not label VendorProof “submitted” until Devpost provides positive submitted
  state evidence.

Read status in this order:

1. live Devpost/account/cloud/provider state;
2. current repository, CI, tests, and deployment;
3. `NEXT.md` and `docs/DEPLOYMENT.md`;
4. this development log;
5. old chat or memory snapshots.

## 13. Common verification commands

```bash
cd /Users/simon/Documents/1-Projects/36、VendorProof
uv sync --frozen
uv run ruff check .
uv run pytest --cov=vendorproof --cov-report=term-missing -q
uv run python scripts/live_smoke.py
```

The live smoke command requires real provider configuration and is expected to
fail before the account/secret gate is completed. That failure is not a test
substitute and must not be reclassified as a successful integration.
