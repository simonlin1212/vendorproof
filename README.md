<p align="center"><b>English</b> | <a href="README_zh.md">简体中文</a></p>

<h1 align="center">VendorProof</h1>

<p align="center">
  <b>Make vendor decisions from live evidence, not stale spreadsheets.</b><br>
  Real-time web research · Exact citations · Risk signals · Refresh history
</p>

<p align="center">
  <a href="https://github.com/simonlin1212/vendorproof/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/simonlin1212/vendorproof/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-19312c">
  <img alt="40 tests" src="https://img.shields.io/badge/tests-40%20passing-c8f74a">
  <img alt="coverage 94%" src="https://img.shields.io/badge/coverage-94%25-ff5b3d">
  <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-19312c">
</p>

<p align="center">
  <a href="#the-problem">Problem</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#run-locally">Run locally</a> ·
  <a href="DEV_LOG.md">Development log</a>
</p>

---

![VendorProof procurement brief interface](assets/screenshots/vendorproof-cloud-run.png)

VendorProof is an evidence-first AI procurement desk for small teams. Paste a
software or supplier brief and it checks the decision-critical claims against
current Google web and news results through SerpApi. Gemini classifies each
claim as supported, changed, conflicting, or insufficient, but it may cite only
the exact URLs returned in that live search. Xano stores the brief and evidence
snapshots so a later refresh can show what changed.

This standalone project targets the SerpApi and Xano cash tracks of the
[DevNetwork API + Cloud + AI Hackathon 2026](https://api-cloud-ai-hackathon-2026.devpost.com/).

## The problem

Vendor comparisons often live in spreadsheets that go stale as soon as prices,
limits, integrations, or reliability change. General AI answers make the
problem worse when they hide uncertainty or invent citations.

VendorProof turns that spreadsheet into a repeatable evidence file:

- live web and news research for each critical claim;
- exact, clickable source URLs;
- visible contradictions and incomplete searches;
- a conservative `publish`, `review`, or `hold` decision;
- persisted snapshots that make changes auditable.

## How it works

1. Gemini converts a bounded procurement brief into at most five verifiable
   claims and focused search queries.
2. SerpApi runs Google Light and Google News searches for each claim.
3. Gemini evaluates only the returned evidence and produces a structured
   assessment.
4. A provenance guard removes citations that were not observed byte-for-byte in
   the current SerpApi response and downgrades unsupported conclusions.
5. Partial search failures remain visible and can never produce a silent
   all-clear.
6. Xano saves the brief and complete report as a new evidence snapshot.

## Architecture

```text
Browser
  |
  v
Flask / Cloud Run
  |-- Gemini 3.5 Flash: claim extraction + evidence assessment
  |-- SerpApi: Google Light + Google News live results
  |-- Provenance guard: exact URL matching + uncertainty enforcement
  `-- Xano: briefs, snapshots, and change receipts
```

Provider credentials stay server-side. The browser never receives the SerpApi
key, Xano token, or Google credentials.

## Safety and evidence guarantees

- Inputs are normalized and capped at 12,000 characters.
- Each run checks no more than five claims and twenty sources per claim.
- URLs keep the provider's exact bytes while rejecting malformed or
  control-containing values.
- Definitive verdicts without a current observed citation are downgraded.
- A failed evidence channel is displayed, never treated as “no risk.”
- Model output is validated with Pydantic before rendering or persistence.
- The live smoke test fails unless one complete claim has real search evidence.

## Run locally

Requirements: Python 3.12, `uv`, Google Vertex AI access, and a SerpApi key.
Xano is optional for local UI work but required for the Xano sponsor track.

```bash
uv sync --frozen
cp .env.example .env
# Fill the server-side values in .env, then authenticate Google locally.
gcloud auth application-default login
uv run gunicorn --bind :8080 --workers 1 --threads 8 --timeout 180 wsgi:app
```

Open `http://127.0.0.1:8080/`. Run the release checks with:

```bash
uv run ruff check .
uv run pytest --cov=vendorproof --cov-report=term-missing -q
uv run python scripts/live_smoke.py
```

The Xano schema and endpoint contract are documented in
[docs/XANO_BACKEND.md](docs/XANO_BACKEND.md).

## Deployment

The repository includes a reproducible Python 3.12 container image. Production
deployment uses Cloud Run with secrets supplied as runtime environment values.
The public demo URL will be added after the real SerpApi and Xano integration
smoke test passes. The current health-only deployment and its promotion gate are
recorded in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Verification status

- 40 tests passing
- 94% branch-aware project coverage
- Ruff clean
- Google Vertex AI structured-output smoke passed with `gemini-3.5-flash`
- Independent code review converged to no actionable regressions
- Live SerpApi + Xano smoke pending account access

See [DEV_LOG.md](DEV_LOG.md) for dated evidence and [NEXT.md](NEXT.md) for the
current release gate.

## License

MIT. See [LICENSE](LICENSE).

**Author:** Simon Lin · X [@linsizhen](https://x.com/linsizhen) · Email: [simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)

## Support

If this project saves a procurement team from one stale spreadsheet, coffee is
welcome.

<p align="center">
  <a href="https://buymeacoffee.com/simonlin1212"><img src="./assets/bmc-qr.png" width="180" alt="Buy Me a Coffee"></a>
</p>
