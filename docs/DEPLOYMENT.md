# VendorProof deployment record

Updated: 2026-08-30 Asia/Singapore

## Google Cloud resources

- Project: `our-episode-506708-k6`
- Region: `asia-southeast1`
- Cloud Run service: `vendorproof-web`
- Runtime identity:
  `vendorproof-runtime@our-episode-506708-k6.iam.gserviceaccount.com`
- Runtime role: `roles/aiplatform.user`
- Production URL:
  `https://vendorproof-web-qjv2kumm3q-as.a.run.app`
- First ready revision: `vendorproof-web-00001-hzf`
- Accepted production revision: `vendorproof-web-00003-qeg` (100% traffic)
- Source build: `37c2aa90-e4bb-4cbe-9e25-4947b1701f92`

The runtime identity is separate from Agentic Brief and ScriptProof. The
service is capped at two instances and can scale to zero.

## Xano resources

- Workspace: `167898`, free plan, United States region
- API group: `vendorproof` (`430337`)
- Snapshot endpoint: `4027876`
- Published URL:
  `https://x8ki-letl-twmt.n7.xano.io/api:vendorproof/snapshots`
- Google Secret Manager secret: `vendorproof-xano-api-token`, version `2`

The credential value is not recorded here. The endpoint requires it before any
normalization, comparison, or write. Xano live acceptance and the Python adapter
smoke passed; details are in [XANO_BACKEND.md](XANO_BACKEND.md).

Version `1` contained a trailing newline from the original provisioning path.
Xano correctly rejected that credential. Version `2` stores the exact 64-byte
token with no trailing whitespace; version `1` remains available only for
rollback evidence.

## Verified production behavior

- `GET /` returns the complete VendorProof interface.
- `GET /health` returns HTTP 200 with
  `{"service":"vendorproof","status":"ok"}`.
- The production page passed a browser render assertion.
- Zero-traffic candidate revision `vendorproof-web-00003-qeg` completed the
  three-vendor Gemini + SerpApi + Xano smoke and wrote Xano snapshot `46`.
- Browser functional submission on the candidate returned a real `publish`
  dossier with an exact citation and Xano snapshot `47`.
- Exact mobile emulation at 390×844 reported no horizontal overflow.
- After promotion to 100% traffic, the production smoke returned HTTP 200 in
  12.4 seconds with live evidence and Xano snapshot `48`.
- GitHub Actions run `33291331586` passed for release commit `3aac90d`.

## Promotion gate result

All promotion items passed on 2026-08-30:

1. Explicit SerpApi version `1` and Xano version `2` were attached to the
   zero-traffic candidate.
2. The real provider chain passed candidate smoke.
3. Browser QA verified the result, citation, Xano receipt, and responsive layout.
4. The accepted revision was promoted, production was re-smoked, screenshots
   were captured, and the public demo video was produced.

The working demo, video, and submission are:

- `https://vendorproof-web-qjv2kumm3q-as.a.run.app/`
- `https://youtu.be/z9RUGx1DMT8`
- `https://devpost.com/software/vendorproof`

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
