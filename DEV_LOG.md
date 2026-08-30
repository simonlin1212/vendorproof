# VendorProof development log

Updated: 2026-08-30 Asia/Singapore

## 1. Current status

VendorProof is the submitted and judging-frozen third hackathon project. It is
an evidence-first procurement desk for the DevNetwork [API + Cloud + AI]
Hackathon 2026, targeting the SerpApi and Xano cash tracks.

The codebase, test suite, public repository, production deployment, public demo
video, Devpost entry, and Xano backend are complete. VendorProof was formally
submitted on 2026-08-30. Devpost showed both `Project submitted!` and
`SUBMITTED TO DevNetwork [API + Cloud + AI] Hackathon 2026` on the public
project page.

| Area | State | Evidence |
|---|---|---|
| Source repository | Public | `https://github.com/simonlin1212/vendorproof`; XanoScript is included under `xano/` in this update |
| CI | Passing | Release run `33291331586` passed for code commit `3aac90d`; run `33302070873` passed for submission-record commit `004c116` |
| Unit/regression tests | Passing | 391 tests, 95.26% whole-project coverage |
| Static quality | Passing | Ruff clean |
| Gemini | Verified separately | Vertex AI structured-output smoke passed with `gemini-3.5-flash` in `global` |
| Web UI | Implemented and checked | Desktop/mobile render plus browser functional assertions passed |
| Cloud Run | Production accepted | `vendorproof-web-00003-qeg` at 100% traffic; public URL returns the working dossier interface |
| Real analysis | Production live smoke passed | Candidate snapshot `46`, browser snapshot `47`, production snapshot `48`; production HTTP 200 in 12.4 seconds |
| Devpost | `SUBMITTED` | Project `1160958`, `https://devpost.com/software/vendorproof`, both cash sponsor tracks selected |
| SerpApi account | Verified and secured | API key is stored as Secret Manager version `1`; only the VendorProof runtime identity has access |
| Xano workspace | Published and live-tested | Workspace `167898`, API group `430337`, endpoint `4027876`; adapter receipt `snapshot_id=9`, concurrent snapshots `13`–`14`, v4 migration snapshots `33`–`35`, v5 acceptance snapshots `36`–`41`, final release snapshots `46`–`48` |
| Demo video | Public | 3:15, `https://youtu.be/z9RUGx1DMT8`; YouTube Studio confirms `Public` and no policy issue |
| Video backup | Public download verified | Google Drive returned HTTP 200, `video/mp4`, and the exact 8,630,407-byte file without authentication |
| Final submission | Complete | Public preview, images, story, links, video, backup, terms, and both sponsor tracks verified before submit |

The status words above are deliberate. The production claim is based on a real
three-provider dossier and Xano receipt, not a health route. The submission
claim is based on Devpost's positive submitted state, not a completed form.

### 1.1 Two-day production overview

VendorProof went from sponsor-track selection to a positively confirmed
Devpost submission in two focused calendar days: 2026-08-29 and 2026-08-30.
The duration matters because the project did not stop at a prototype or a
healthy web page; it completed real sponsor integrations, release hardening,
production acceptance, a public demo, and the final submission state.

| Day | Main production work | End-of-day gate |
|---|---|---|
| 2026-08-29 — foundation and sponsor backend | Selected one coherent procurement product for the SerpApi and Xano cash tracks; built the typed Gemini/SerpApi/Xano pipeline, deterministic provenance guard, Flask UI, live-smoke tooling, tests, public repository, CI, bilingual documentation, and Cloud Run preproduction; registered Simon for the event from Hong Kong; provisioned and repeatedly hardened the Xano backend through deterministic identity, migration, and concurrency tests. | Public code, CI, browser UI, Cloud Run shell, Devpost registration, and the real Xano endpoint were ready. SerpApi was still behind human account verification, so `/analyze` correctly failed closed with HTTP 503 and the project remained explicitly unsubmitted. |
| 2026-08-30 — real integration, release, media, and submission | Cleared SerpApi verification; stored provider credentials in Secret Manager; passed the real Gemini + SerpApi + Xano smoke; expanded the regression suite to 391 tests; converged independent review; pushed release commit `3aac90d`; corrected the newline-contaminated Xano secret by creating exact version 2; accepted candidate snapshots `46` and `47`; promoted revision `vendorproof-web-00003-qeg`; passed production snapshot `48`; completed desktop/mobile QA; produced and published the 3:15 demo; verified the public MP4 backup; completed the Devpost story, gallery, links, terms, and both cash tracks. | Devpost project `1160958` showed `Project submitted!` and `SUBMITTED TO`; the later reload still showed the submitted state. Submission-record commit `004c116` passed GitHub Actions run `33302070873`, after which all judged materials entered the freeze. |

This was therefore a two-day production closeout, not a two-day background
process left running. The first day established and challenged the product and
integration architecture. The second day converted that foundation into a
verified production release and an accepted competition submission.

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
- Unmappable generated checks stay visible and force `review`; they never vanish
  silently or fail the whole evidence run when other checks remain valid.
- Provider output is validated with Pydantic before rendering or persistence.
- Xano receives the validated complete report snapshot, not a second model
  summary that could drift from the displayed result.
- Each extracted claim carries a `comparison_key` derived from deterministic
  entity and requirement atoms in the immutable brief. Mutable prose,
  model-supplied domains, shorter nested anchors, and classifications cannot
  alter identity.
- Xano serializes each brief's compare-and-write operation with a transaction
  and row lock, so simultaneous refreshes cannot share a stale predecessor.
- Xano rejects requests unless the server-only `api_token` matches its private
  workspace environment variable. The value is carried only over HTTPS between
  Cloud Run and Xano and is not rendered in the browser.
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

- 391 tests pass.
- Whole-project coverage is 95.26%, including branches.
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

The earlier implementation completed five independent finding rounds and a
clean re-review. The Xano integration then went through repeated independent
review and repair rounds. They found missing-token handling, mutable prose
identity, a concurrent stale-predecessor race, legacy key migration, silently
rejected anchors, decimal segmentation, same-category collisions, ambiguous
model classifications, and vendor full-name/acronym drift. All findings were
fixed in code or XanoScript and covered by regression or live acceptance tests.
The final v5 identity uses deterministic entity and requirement atoms from the
brief. Model-supplied domains and classifications remain descriptive metadata
only.

The final public-release review added adversarial coverage for infix comparisons,
shortlists, Chinese directives, dotted initialisms, legal suffixes, single-vendor
aliases, and same-name companies. VendorProof first confirms the entity-to-domain
mapping independently. It then accepts third-party evidence only when the exact
entity identity remains visible and the surrounding result metadata does not name
a different compound entity. The review converged with no remaining actionable
findings.

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

## 9. Submission package preparation checkpoint (historical)

At this pre-submission checkpoint, the following materials existed but were not
yet final submission evidence:

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

The first public-release foundation converged at 100 tests and 94.81% coverage,
completed its independent review loop, verified the interface in a browser,
created the public GitHub repository, and added passing CI. Subsequent sponsor
integration hardening later expanded the suite to 159 tests at 94.82%
coverage at that checkpoint.

### 2026-08-29 — preproduction deployment

Created a dedicated runtime identity and deployed Cloud Run revision
`vendorproof-web-00001-hzf`. Verified the public home and health routes and the
intentional HTTP 503 on unconfigured analysis. Updated public architecture copy
to distinguish the Cloud Run application from external Gemini, SerpApi, and
Xano services.

### 2026-08-29 — account blocker confirmed

The first account pass reached human registration gates on Devpost, SerpApi,
and Xano, so the project correctly remained unsubmitted rather than claiming a
false live integration.

### 2026-08-29 — Devpost registration completed

Completed the participant profile and registered Simon for the DevNetwork event
with Hong Kong as the participation location. The submission management page is
available, but no empty project was created because a real working demo remains
the submission gate.

### 2026-08-29 — Xano backend provisioned and accepted

Created the free Xano workspace resources used by VendorProof:

- `briefs` table with unique deterministic `brief_hash`;
- `snapshots` table related to `briefs`, storing the complete validated report;
- `POST https://x8ki-letl-twmt.n7.xano.io/api:vendorproof/snapshots`;
- private workspace environment variable checked before any data processing;
- corresponding Xano credential in Google Secret Manager, with no value printed
  or committed.

The first comparison implementation used AI-generated array filtering but
incorrectly returned zero changes. An attempted associative-diff filter also
failed at Xano runtime. The final published implementation uses explicit nested
loops and was exercised against the live data source: no prior snapshot returned
`0`, a verdict change returned `1`, an added claim returned `1`, and one removal
plus one verdict change returned `2`. The real Python adapter then wrote snapshot
`9`, proving the application contract matches the published endpoint.

An independent follow-up review caught two deeper refresh-history risks. Exact
claim prose was too unstable to serve as identity because Gemini may paraphrase
the same fact, and two simultaneous writes could both read the same predecessor.
The extractor now emits exact vendor and requirement anchors from the brief, an
official domain, and a fixed check category. The application rejects anchors
not present in the input, requires complete entity spans, retains the validated
exact entity name, maps requirement spans to deterministic brief atoms, binds
search queries to those entities, derives v5 `comparison_key` from entity names
and requirement atoms, deduplicates by it, and Xano
compares it inside a per-brief transaction protected by a row lock. Live
snapshots `10` and `11` proved that paraphrasing with the same key produces zero
changes, snapshot `12` proved a verdict change produces one, and simultaneous
snapshots `13` and `14` proved that the second write names the first as its
predecessor and records the changed verdict. A final legacy sequence, snapshots
`18`–`20`, proved that an old keyless report receives one zero-change baseline
before normal verdict-change tracking resumes. Snapshots `33`–`35` then proved
the v4 migration path: a v3 predecessor produced a zero-change baseline,
followed by exactly one change for a v4 verdict transition. The published v5
schema adds an explicit report-level comparison version so valid empty current
snapshots remain comparable. Snapshots `36`–`39` proved unchanged, verdict-change,
and domain-change behavior; snapshots `40`–`41` proved an empty report can become
one added claim. The application binds domains written beside vendors in the
brief and otherwise requires an independent Google knowledge-panel confirmation.
Evidence from a same-name company domain is excluded before assessment.

The authentication transport was changed from an unreliable request-header
lookup to a required `api_token` body field over HTTPS. The Python adapter,
tests, public contract, and XanoScript source were updated together. Ruff and all
159 tests passed at that checkpoint. Independent review found and closed missing-token fail-closed,
claim-identity, concurrency, legacy migration, common comparison separator,
exact entity-query, Unicode entity matching, descriptive namesake, compound
namesake-domain, and public-suffix gaps. Each fix has a regression test.

A final release review then found and closed full-URL vendor annotations,
subject-prefixed and quantified global requirements, later-acronym identity
drift, legal-suffix sentence splitting, thousands-separated budgets,
entity-only requirement identities, and third-party namesake evidence without
an explicit verified-domain link. The final pass also isolated requirements in
trailing comparison scopes and accepted ordinary source titles when the brief
used an equivalent legal company suffix. The last input pass made `vs.` and
legal-suffix periods context-aware, aligned bracketed domain annotations, kept
budget constraints separate from following directives, normalized annotated
entity anchors and legal-name lists, and strengthened the live smoke gate to
require an observed citation. A final adversarial round then preserved both
vendors in infix `vs` comparisons, applied shared shortlist requirements to every
listed vendor, separated Chinese requirement tails from company names, and
required explicit official-domain metadata on third-party evidence after identity
confirmation. The converged release suite is 391 tests at 95.26% branch-aware
whole-project coverage, with Ruff clean.

The real Vertex AI extraction smoke then processed the annotated sample brief
with Gemini 3.5 Flash and returned eight valid checks across Intercom, Zendesk,
and Crisp, with zero rejected anchors. This verifies the extraction and brief
binding layer independently of search.

### 2026-08-30 — SerpApi gate cleared and complete live smoke accepted

Simon completed SerpApi account verification. The private key was stored in
Google Secret Manager as `vendorproof-serpapi-api-key` version `1`; it was not
written to the repository or ordinary environment configuration. Secret
Accessor was granted only to the standalone VendorProof runtime identity.

`scripts/live_smoke.py` then completed a real Gemini 3.5 Flash + SerpApi Google
web/news + Xano run. It returned five procurement claims, preserved conservative
`insufficient` states where evidence was incomplete, produced live citations,
and wrote Xano snapshot `42`. This cleared the local integration gate but did
not yet prove the deployed service.

### 2026-08-30 — release review, candidate acceptance, and production promotion

The final release diff passed Ruff, all 391 tests, 95.26% branch-aware coverage,
`git diff --check`, Gitleaks history and worktree scans, and an independent
focused review that returned `No actionable regressions.` Release commit
`3aac90d` was pushed to `main`; GitHub Actions run `33291331586` completed
successfully. Repository Secret Scanning and Push Protection were enabled.

Cloud Run candidate revision `vendorproof-web-00003-qeg` was deployed with
explicit Secret Manager versions. The first Xano secret version contained a
trailing newline, so the exact token check failed closed. Version `2` was
created as the exact 64-byte value without trailing whitespace. No source-code
workaround was added, and version `1` was preserved as rollback evidence.

The candidate then passed three distinct gates:

- a small full-provider run wrote Xano snapshot `45`;
- the complete three-vendor sample returned HTTP 200 with five critical checks,
  four evidence blocks, and Xano snapshot `46`;
- browser submission produced a real `publish` dossier, an exact citation, and
  Xano snapshot `47`.

Desktop visual QA passed. Exact 390×844 mobile emulation reported
`scrollWidth=390` and no horizontal overflow. The accepted revision was promoted
to 100% production traffic. A fresh production smoke returned HTTP 200 in 12.4
seconds with live evidence and Xano snapshot `48`.

### 2026-08-30 — demo production and Devpost submission

A 1920×1080 English demo was produced from the real deployed interface,
architecture, evidence file, Xano receipt, and release metrics. The final cut is
3:15 with hard subtitles. An independent speech-to-text pass reached more than
90% word-sequence agreement and confirmed the closing lines were present.

YouTube Studio completed its checks with no issue and published the video as
`Public` at `https://youtu.be/z9RUGx1DMT8`. A byte-identical MP4 backup was
uploaded to Google Drive, changed to `Anyone with the link`, and verified without
authentication as HTTP 200 `video/mp4` with content length `8,630,407` bytes.

Devpost project `1160958` was completed with:

- the production Cloud Run URL and public GitHub repository;
- the public 3:15 YouTube demo;
- three captioned 3:2 gallery images plus the primary thumbnail;
- the full build story, two-day build window, technical stack, and Xano logic;
- `SerpApi – Best AI Use Case` and `Xano: Rebuild a SaaS Tool You Hate`;
- the public downloadable MP4 backup; and
- accepted terms and conditions.

The final click redirected to `https://devpost.com/software/vendorproof` and
showed `Project submitted!` plus `SUBMITTED TO DevNetwork [API + Cloud + AI]
Hackathon 2026`. This is the positive evidence for the submitted claim.

### 2026-08-30 — closeout documentation and post-submission recheck

The project configuration, current handoff, detailed log, and Codex memory were
synchronized around the two-day production window and judging freeze. The
documentation-only repository change was checked with Ruff, all 391 tests at
95.26% branch-aware coverage, `git diff --check`, and Gitleaks history plus
worktree scans. Desktop rendering remained visually intact. Exact 390×844 mobile
emulation reported `innerWidth=390`, `scrollWidth=390`, and no horizontal
overflow.

The public home and health routes returned HTTP 200. Two additional real
production analyses also returned HTTP 200 cited dossiers, in 71.1 and 72.1
seconds respectively. The full three-vendor sample returned five checks and four
citation blocks; the smaller Intercom-only retry returned five checks and three
citation blocks. Neither run produced a new Xano snapshot. In both cases the UI
visibly reported that history was not saved because the official-domain identity
guard could not confirm every vendor from that run's current search evidence.

This post-submission result is recorded as degraded persistence, not a new
three-provider acceptance. The application still returned the evidence file and
did not fabricate a Xano receipt or hide the warning. It does not erase the
accepted candidate/browser/production snapshots `46`–`48`, but future status
reports must not imply that these two closeout runs wrote new snapshots. The
judged code remains frozen; monitor the condition and do not weaken the identity
guard merely to force persistence.

## 11. Post-submission freeze checklist

The release and submission checklist is complete. During judging:

1. Keep repository, video, Cloud Run revision, and Devpost materials frozen.
2. For an availability or security incident, make the smallest necessary fix.
3. Before any submitted-material change, rerun Ruff, the full tests, real
   production smoke, desktop/mobile QA, and secret scans.
4. After any change, re-open Devpost and confirm the project remains submitted.
5. Rotate provider credentials after judging if the public demo remains online,
   then repeat the zero-traffic candidate and production gates.

No fake provider, seeded citation, stub result, or fallback report may be used
for future demos or maintenance validation.

## 12. Project boundaries and source of truth

- Agentic Brief and ScriptProof are already submitted and frozen. VendorProof
  must remain an independent repository, Cloud Run service, identity, secrets,
  Devpost project, and development log.
- `.env` and credentials must never be committed or printed in logs.
- The production and submitted labels are now accepted by the evidence above.
  Preserve the same distinction for future changes.

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
