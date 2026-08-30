# VendorProof — Devpost submission copy

Status: submitted on 2026-08-30 to DevNetwork [API + Cloud + AI] Hackathon
2026, project `1160958`.

## Project name

VendorProof

## Tagline

An evidence-first AI procurement desk that turns a messy vendor brief into a
live, cited decision file.

## Elevator pitch

Vendor comparisons go stale fast. VendorProof checks pricing, capabilities,
limits, and recent risk signals against current Google web and news results via
SerpApi. Gemini evaluates the evidence, but an enforcement layer rejects any
citation that was not returned in the current search. Xano stores every brief
and evidence snapshot so the next refresh can show what changed.

## Inspiration

Small teams often choose software from a spreadsheet assembled during a short
buying window. A month later the prices, limits, integrations, and service
record may already be different. General AI tools can make the comparison
faster, but a confident answer with an invented or stale citation is worse than
the original spreadsheet. VendorProof was built to make freshness,
contradictions, and missing evidence visible before a team commits.

## What it does

1. Converts a procurement brief into at most five decision-critical claims.
2. Searches live Google web and news results through SerpApi.
3. Classifies each claim as supported, changed, conflicting, or insufficient.
4. Allows only exact URLs observed in that current SerpApi run.
5. Downgrades conclusions when citations are missing or one search channel
   fails.
6. Produces a publish, review, or hold decision file.
7. Saves the brief and report in Xano as an auditable evidence snapshot.

## How we built it

The product is a Python 3.12 Flask application deployed as a container on
Google Cloud Run. Gemini 3.5 Flash provides structured claim extraction and
evidence assessment. SerpApi supplies Google Light and Google News results at
runtime. Pydantic validates model output and URL contracts. A separate
provenance guard compares citations byte-for-byte against the live results.
Xano stores briefs and JSON evidence snapshots through a server-to-server API;
provider credentials never reach the browser.

## How Xano is used

Xano replaces the spreadsheet history layer. It owns the `briefs` and
`snapshots` records, finds or creates a normalized brief, locks that brief inside
a database transaction, loads the previous snapshot, and compares keys that
VendorProof maps exact model anchors back to deterministic entity and requirement
atoms in the immutable brief. Model-supplied domains and fact categories remain
descriptive metadata, so shorter nested phrases, aliases, or classifications cannot change
persistent identity. It then saves the complete report and returns a compact
receipt. This avoids false changes and stale concurrent predecessors.

## Challenges

The hardest problem was not generating an answer. It was enforcing an honest
boundary between live evidence and model output. URL normalization can silently
change a citation, partial provider failures can look like empty results, and a
smoke test can pass even when no complete evidence run occurred. Independent
review rounds found these edge cases, and each one now has a regression test.

## Accomplishments

- Exact live-source citation enforcement
- Visible partial-search and persistence failures
- Visible rejected-anchor warnings that force review instead of silent omission
- Conservative decision states instead of false certainty
- 391 passing tests with 95.26% branch-aware coverage
- Complete candidate Gemini + SerpApi + Xano smoke with Xano snapshot 46
- Browser functional evidence file with Xano snapshot 47
- Promoted production smoke with Xano snapshot 48
- Independent review converged with no remaining actionable findings
- Responsive procurement-dossier interface
- Reproducible Python 3.12 deployment image

## What we learned

Structured model output is only the beginning of reliability. The application
still needs to validate URL semantics, preserve provider provenance, re-check
data after transformations, and treat integration smoke tests as evidence
rather than ceremony. The most useful AI procurement tool is one that is
comfortable saying “insufficient evidence.”

## What's next

Add scheduled refreshes, vendor-specific watchlists, richer snapshot diffs, and
team review notes. The current architecture can also support supplier due
diligence beyond software once domain-specific evidence policies are added.

## Built with

Python 3.12, Flask, Gemini 3.5 Flash, Google Vertex AI, SerpApi Google Light,
SerpApi Google News, Xano, Pydantic, Cloud Run, Docker, pytest, Ruff.

## Submission links

- Live demo: `https://vendorproof-web-qjv2kumm3q-as.a.run.app/`
- Source code: `https://github.com/simonlin1212/vendorproof`
- Demo video: `https://youtu.be/z9RUGx1DMT8`
- Devpost: `https://devpost.com/software/vendorproof`
- Downloadable video backup:
  `https://drive.usercontent.google.com/download?id=1AkYmkJvLlEonpPjU1AZfAFE3yksbvZPq&export=download&confirm=t`
- Primary image: `assets/screenshots/vendorproof-devpost-2026-08-30.png`

## Sponsor categories

- SerpApi – Best AI Use Case
- Xano: Rebuild a SaaS Tool You Hate
