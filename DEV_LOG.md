# VendorProof development log

## 2026-08-29 — project start

### Decision

Created a standalone repository at
`/Users/simon/Documents/1-Projects/36、VendorProof` for the DevNetwork
[API + Cloud + AI] Hackathon 2026.

Selected the SerpApi and Xano sponsor tracks because both have explicit cash
awards, accept adult participants from Hong Kong, and can be served by one
coherent product rather than two rushed demos.

### Product definition

VendorProof helps a small team compare software or suppliers without relying on
stale spreadsheets or uncited AI answers. One run will:

1. turn a procurement brief into a bounded checklist of verifiable questions;
2. create focused searches for pricing, features, limits, and recent risks;
3. call SerpApi web and news search;
4. classify each vendor claim as supported, changed, conflicting, or
   insufficient;
5. persist briefs and evidence snapshots in Xano and show what changed between
   refreshes.

### Implemented foundation

- Pydantic contracts for claims, sources, verdicts, and reports.
- Bounded input, deduplication, search-failure handling, and overall risk state.
- Citation-provenance guard: definitive verdicts are downgraded unless at least
  one cited URL was observed in the current SerpApi run.
- Forty unit tests passing with 94% whole-project coverage.
- Five independent review rounds plus a final clean re-review completed. Six
  initial evidence-safety and deployment findings plus seven follow-up boundary
  regressions were fixed and covered by new tests.
- Google Vertex AI smoke test passed with `gemini-3.5-flash`; the sample brief
  produced a structured eight-item verification checklist.
- Responsive procurement-dossier interface implemented and visually checked in
  the in-app browser.
- English and Chinese public documentation, a verified interface screenshot,
  Devpost submission copy, and a 2.5-minute demo script prepared.
- Xano persistence contract and server-side adapter implemented; live workspace
  provisioning is pending account access and a verified zero-cost checkout.

### Guardrails

- Search results are evidence candidates, not automatic truth.
- Public citations must be observed in the current SerpApi response.
- The model cannot invent or rewrite citation URLs.
- Existing submitted hackathon repositories remain untouched.
