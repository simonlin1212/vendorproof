# VendorProof deployment record

Updated: 2026-08-29 Asia/Singapore

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

## Verified preproduction behavior

- `GET /` returns the complete VendorProof interface.
- `GET /health` returns HTTP 200 with
  `{"service":"vendorproof","status":"ok"}`.
- The production page passed a browser render assertion.
- `POST /analyze` currently returns a visible HTTP 503 provider error because
  no SerpApi secret is configured. This is intentional: preproduction must not
  fabricate evidence or silently use a different provider.

## Promotion gate

The URL must not be entered as the Devpost working demo until every item below
passes:

1. Store the real SerpApi key in Secret Manager and grant only the VendorProof
   runtime identity access.
2. Provision the Xano snapshot endpoint and store its server token in Secret
   Manager.
3. Run `scripts/live_smoke.py` against Gemini, SerpApi, and Xano.
4. Submit the sample brief through the public page and verify exact clickable
   citations plus an Xano snapshot receipt.
5. Capture the real evidence-file screenshot and record the demo video.

## Non-secret runtime configuration

```text
GOOGLE_CLOUD_PROJECT=our-episode-506708-k6
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=TRUE
VENDORPROOF_MODEL=gemini-3.5-flash
```

Secret values must never be passed as plain command-line arguments or committed
to this repository.
