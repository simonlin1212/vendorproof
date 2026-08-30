# VendorProof — current handoff

Updated: 2026-08-30 Asia/Singapore

## Current state

- Independent public repository:
  `https://github.com/simonlin1212/vendorproof`.
- Devpost account and DevNetwork event registration are complete for Simon's
  Hong Kong participation.
- Product direction is fixed: an evidence-first vendor and software procurement
  desk targeting the SerpApi and Xano cash tracks.
- Application, tests, interface, deployment image, demo script, and submission
  copy are implemented.
- 391 tests pass at 95.26% coverage and Ruff is clean.
- The previous independent review converged; the final release diff is awaiting
  one clean re-review before push.
- Gemini 3.5 Flash structured-output smoke passed on Vertex AI.
- Xano is fully provisioned and published: the live endpoint is token-protected,
  the Python adapter wrote a real receipt, v5 identity maps model anchors back
  to deterministic brief atoms while excluding model-supplied domains, old
  identity formats establish a clean baseline,
  and simultaneous writes serialize per brief.
- The published v5 endpoint passed live acceptance in snapshots `36`–`41`:
  unchanged refresh `0`, verdict change `1`, domain change `1`, and an
  empty-to-added transition `1`.
- A real Gemini extraction of the annotated sample returned eight valid checks
  across Intercom, Zendesk, and Crisp with zero rejected anchors.
- SerpApi is verified, its key is stored in Google Secret Manager, and only the
  VendorProof runtime identity has access.
- The complete local Gemini + SerpApi + Xano live smoke passed with five claims,
  live citations, and Xano snapshot `42`.
- The Cloud Run preproduction service is healthy; the accepted integration still
  needs deployment to a zero-traffic candidate and browser QA.

## Immediate next actions

1. Complete the final independent review, fix any actionable finding, and push
   the verified release diff.
2. Attach both explicit secret versions to a zero-traffic Cloud Run candidate.
3. Run the complete Gemini + SerpApi + Xano candidate smoke and browser QA.
4. Promote the verified revision, capture the real report, and record the
   2–4-minute demo.
5. Complete the Devpost entry, select both cash tracks, submit, and re-open the
   management page to record positive `SUBMITTED` evidence.

## Frozen decisions

- Do not modify the submitted Agentic Brief or ScriptProof projects.
- Xano is a meaningful backend, not an optional badge: it owns normalized briefs,
  immutable report snapshots, and deterministic change counts.
- Do not claim a verdict is supported unless at least one public citation came
  from the current SerpApi run.
- Do not promote the public demo, record the demo video, or submit Devpost using
  stub or seeded evidence.
