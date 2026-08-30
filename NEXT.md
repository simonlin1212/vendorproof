# VendorProof — current handoff

Updated: 2026-08-30 Asia/Singapore

## Current state

- Official Devpost submission:
  `https://devpost.com/software/vendorproof` (`SUBMITTED`, project `1160958`).
- Public production demo:
  `https://vendorproof-web-qjv2kumm3q-as.a.run.app/`.
- Public demo video:
  `https://youtu.be/z9RUGx1DMT8` (3:15, public).
- Independent public repository:
  `https://github.com/simonlin1212/vendorproof`.
- Simon is registered from Hong Kong and the submission targets the two cash
  sponsor tracks: `SerpApi – Best AI Use Case` and
  `Xano: Rebuild a SaaS Tool You Hate`.
- 391 tests pass at 95.26% coverage and Ruff is clean.
- The release code is commit `3aac90d`; GitHub Actions run `33291331586`
  passed, independent review converged with no actionable regression, and
  GitHub Secret Scanning plus Push Protection are enabled.
- Production is Cloud Run revision `vendorproof-web-00003-qeg` at 100% traffic.
- Gemini 3.5 Flash structured-output smoke passed on Vertex AI, and the final
  production smoke completed the Gemini + SerpApi + Xano chain in 12.4 seconds.
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
- Candidate acceptance produced full-chain snapshot `46`; browser functional QA
  produced snapshot `47`; the promoted production smoke produced snapshot `48`.
- Desktop QA, exact 390×844 mobile emulation, public video playback, Devpost
  preview, the two sponsor selections, and the public Drive backup were all
  verified before submission.

## Immediate next actions

1. Freeze the submitted repository, live demo, video, and Devpost materials
   until judging ends. Change them only for a security incident or a confirmed
   availability failure.
2. Keep provider spending and Cloud Run usage under observation while the demo
   remains public.
3. After judging, rotate the SerpApi and Xano credentials if the live demo will
   stay online, then redeploy and repeat the full production smoke.

## Frozen decisions

- Do not modify the submitted Agentic Brief or ScriptProof projects.
- Do not modify VendorProof submission materials during the judging freeze
  without rerunning tests, production smoke, visual QA, and Devpost state
  confirmation.
- Xano is a meaningful backend, not an optional badge: it owns normalized briefs,
  immutable report snapshots, and deterministic change counts.
- Do not claim a verdict is supported unless at least one public citation came
  from the current SerpApi run.
- Do not promote the public demo, record the demo video, or submit Devpost using
  stub or seeded evidence.
