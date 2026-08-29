# VendorProof — current handoff

Updated: 2026-08-29 Asia/Singapore

## Current state

- Independent Git repository created.
- SerpApi and Xano cash tracks selected.
- Product direction fixed: evidence-first vendor and software procurement desk.
- Official SerpApi Python SDK and `serpapi-search-tools` reference implementation
  identified.
- The evidence service is implemented with provenance enforcement and 100%
  unit-test coverage for the current core.

## Immediate next actions

1. Implement and test the SerpApi and Gemini adapters.
2. Build the procurement workflow and web interface.
3. Add Xano persistence after the SerpApi vertical slice is verified.
4. Obtain event/API access and run a live integration smoke test.
5. Deploy, record the demo, and submit to both cash tracks.

## Frozen decisions

- Do not modify Agentic Brief or ScriptProof.
- Add Xano only after the SerpApi vertical slice is complete and verified.
- Do not claim a verdict is supported unless at least one public citation came
  from the current SerpApi run.
