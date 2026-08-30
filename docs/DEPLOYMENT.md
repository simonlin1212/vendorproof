# VendorProof deployment record

Updated: 2026-08-30 Asia/Singapore

## Google Cloud resources

- Project: `our-episode-506708-k6`
- Region: `asia-southeast1`
- Cloud Run service: `vendorproof-web`
- Runtime identity:
  `vendorproof-runtime@our-episode-506708-k6.iam.gserviceaccount.com`
- Runtime role: `roles/aiplatform.user`
- Preproduction URL:
  `https://vendorproof-web-qjv2kumm3q-as.a.run.app`
- First ready revision: `vendorproof-web-00001-hzf`
- Source build: `37c2aa90-e4bb-4cbe-9e25-4947b1701f92`

The runtime identity is separate from Agentic Brief and ScriptProof. The
service is capped at two instances and can scale to zero.

## Xano resources

- Workspace: `167898`, free plan, United States region
- API group: `vendorproof` (`430337`)
- Snapshot endpoint: `4027876`
- Published URL:
  `https://x8ki-letl-twmt.n7.xano.io/api:vendorproof/snapshots`
- Google Secret Manager secret: `vendorproof-xano-api-token`, version `1`

The credential value is not recorded here. The endpoint requires it before any
normalization, comparison, or write. Xano live acceptance and the Python adapter
smoke passed; details are in [XANO_BACKEND.md](XANO_BACKEND.md).

## Verified preproduction behavior

- `GET /` returns the complete VendorProof interface.
- `GET /health` returns HTTP 200 with
  `{"service":"vendorproof","status":"ok"}`.
- The production page passed a browser render assertion.
- The original public revision still returns a visible HTTP 503 provider error
  because it intentionally has no SerpApi secret attached.
- The complete local Gemini + SerpApi + Xano live smoke passed and wrote Xano
  snapshot `42`; the same configuration still needs zero-traffic candidate QA.

## Promotion gate

The URL must not be entered as the Devpost working demo until every item below
passes:

1. Attach explicit SerpApi and Xano secret versions to a zero-traffic candidate.
2. Run `scripts/live_smoke.py` against the accepted configuration.
3. Submit the sample brief through the candidate page and verify exact clickable
   citations plus an Xano snapshot receipt.
4. Promote the accepted candidate, capture the real evidence-file screenshot,
   and record the demo video.

## Non-secret runtime configuration

```text
GOOGLE_CLOUD_PROJECT=our-episode-506708-k6
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=TRUE
VENDORPROOF_MODEL=gemini-3.5-flash
XANO_SNAPSHOT_ENDPOINT=https://x8ki-letl-twmt.n7.xano.io/api:vendorproof/snapshots
```

Secret values must never be passed as plain command-line arguments or committed
to this repository.
