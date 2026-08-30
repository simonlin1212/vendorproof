# VendorProof demo script

Target length: 2–4 minutes. The accepted public cut is 3:15 and was produced
only after the production live smoke passed:
`https://youtu.be/z9RUGx1DMT8`.

## 00:00–00:20 — problem

“Vendor comparisons usually end up in a spreadsheet that starts going stale the
day it is made. Prices change, plan limits move, integrations disappear, and a
confident AI answer may cite a page it never actually saw. VendorProof turns a
messy procurement brief into a live, cited evidence file.”

## 00:20–00:40 — input

Show the home page. Load the sample brief comparing Intercom, Zendesk, and Crisp
for a five-person team under a monthly budget. Point out that the brief includes
must-haves and deal-breakers, not a chat question.

## 00:40–01:20 — autonomous research

Click **Build evidence file**. Explain that Gemini extracts at most five
decision-critical claims, then SerpApi runs current Google web and news searches
for each one. No sample result is injected into the production path.

While the result loads, show the architecture slide or repository diagram:

“Gemini proposes and evaluates the checks. SerpApi supplies the live evidence.
The enforcement layer allows only exact URLs returned in this run. Xano stores
the brief and the complete snapshot.”

## 01:20–01:55 — evidence file

Scroll through two result cards. Show:

- the supported, changed, conflicting, or insufficient label;
- the explanation and next action;
- clickable exact citations;
- any visible partial-search warning;
- the overall publish, review, or hold status.

Say: “A missing citation cannot become a confident conclusion. VendorProof
automatically downgrades it to insufficient evidence.”

## 01:55–02:15 — Xano history

Show the Xano snapshot receipt and the Xano table/API response. Refresh the same
brief after a controlled evidence change if available. Point out the previous
snapshot ID and changed-claim count.

“The comparison is no longer a disposable answer. It is an auditable history.”

## 02:15–02:30 — close

“VendorProof replaces the stale comparison spreadsheet with live research,
honest uncertainty, and a record of what changed. Evidence before commitment.”

End on the live product URL and repository URL.
