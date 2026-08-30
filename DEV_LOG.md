# VendorProof development log

Updated: 2026-08-30 Asia/Singapore

## 1. Current status

VendorProof is the active third hackathon project. It is an evidence-first
procurement desk for the DevNetwork [API + Cloud + AI] Hackathon 2026, targeting
the SerpApi and Xano cash tracks.

The codebase, test suite, public repository, Cloud Run preproduction shell,
submission copy, demo script, Devpost registration, and Xano backend are
complete. The project is **not submitted** and the public URL is **not yet a
working demo**: the real three-provider smoke has passed locally, but the
accepted configuration still needs zero-traffic Cloud Run QA and promotion.

| Area | State | Evidence |
|---|---|---|
| Source repository | Public | `https://github.com/simonlin1212/vendorproof`; XanoScript is included under `xano/` in this update |
| CI | Passing | GitHub Actions run `33229641295` |
| Unit/regression tests | Passing | 391 tests, 95.26% whole-project coverage |
| Static quality | Passing | Ruff clean |
| Gemini | Verified separately | Vertex AI structured-output smoke passed with `gemini-3.5-flash` in `global` |
| Web UI | Implemented and checked | Desktop/mobile render plus browser functional assertions passed |
| Cloud Run | Preproduction healthy | `vendorproof-web-00001-hzf`; home and health routes return HTTP 200 |
| Real analysis | Local live smoke passed | Gemini + SerpApi + Xano produced five claims with live citations and Xano snapshot `42` |
| Devpost registration | Complete | Simon's `linsizhen` profile is registered for the event; no empty submission was created |
| SerpApi account | Verified and secured | API key is stored as Secret Manager version `1`; only the VendorProof runtime identity has access |
| Xano workspace | Published and live-tested | Workspace `167898`, API group `430337`, endpoint `4027876`; adapter receipt `snapshot_id=9`, concurrent snapshots `13`–`14`, v4 migration snapshots `33`–`35`, v5 acceptance snapshots `36`–`41` |
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
and wrote Xano snapshot `42`. The remaining release work is final diff re-review,
zero-traffic Cloud Run candidate QA, promotion, demo capture, and Devpost
submission verification.

## 11. Exact resume and promotion checklist

Resume in this order:

1. Complete the final release-diff review and push the verified revision.
2. Deploy a tagged or zero-traffic candidate revision with explicit SerpApi and
   Xano secret versions.
3. Submit the sample procurement brief through the candidate interface.
4. Verify exact clickable SerpApi citations, partial-failure markers,
   conservative verdicts, and a real Xano snapshot receipt.
5. Promote the verified revision to 100% traffic.
6. Capture the real report screenshots and record the demo video.
7. Complete Devpost fields, select both cash tracks, and submit.
8. Re-open the management page and record positive evidence that the entry is
    `SUBMITTED`.

No fake provider, seeded citation, stub result, or fallback report may be used
to bypass steps 2–6.

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
