# Xano backend contract

VendorProof uses Xano as the system of record for procurement briefs and their
evidence snapshots. The frontend never receives Xano credentials.

The deployed backend is also checked into [`../xano/`](../xano/) as XanoScript
so the sponsor integration can be reviewed and reproduced.

## Live deployment

- Workspace: `Simon's Workspace` (`167898`), free plan, United States region
- API group: `vendorproof` (`430337`)
- Endpoint: `POST /snapshots` (`4027876`)
- Base URL: `https://x8ki-letl-twmt.n7.xano.io/api:vendorproof`
- Published endpoint:
  `https://x8ki-letl-twmt.n7.xano.io/api:vendorproof/snapshots`
- Tables: `briefs` (`883456`) and `snapshots` (`883457`)

## Required data model

### `briefs`

- `id`: integer primary key
- `brief_hash`: text, indexed
- `brief_text`: text
- `created_at`: timestamp
- `updated_at`: timestamp

### `snapshots`

- `id`: integer primary key
- `brief_id`: integer, indexed relation to `briefs`
- `generated_at`: timestamp
- `overall_action`: text
- `report_json`: json
- `changed_claims`: integer

## Required API

`POST /vendorproof/snapshots`

Input:

```json
{
  "api_token": "server-to-server credential",
  "brief": "A bounded procurement brief",
  "report": {"comparison_schema": "v5", "generated_at": "...", "overall_action": "review", "claims": []}
}
```

Behavior:

1. Normalize and hash the brief.
2. Find or create its `briefs` record.
3. Open a database transaction and lock that brief's row so simultaneous
   refreshes cannot share a stale predecessor.
4. Load the newest prior snapshot for that brief.
5. Compare verdicts by each claim's stable `comparison_key`, so wording changes
   alone do not count as factual changes.
6. Save the complete new snapshot.
7. Return only the receipt below.

Response:

```json
{
  "snapshot_id": "42",
  "previous_snapshot_id": "37",
  "changed_claims": 2
}
```

The production endpoint is configured through `XANO_SNAPSHOT_ENDPOINT`. The
server-to-server credential is sent over HTTPS as `api_token` and is compared
inside Xano with a workspace environment variable. It is stored only as
`XANO_API_TOKEN` in the deployment secret store and is never exposed to the
browser. Application configuration fails closed if an endpoint is enabled
without the matching token.

## Live acceptance evidence

The published endpoint was exercised against Xano's live data source on
2026-08-29 (Asia/Singapore):

- a first snapshot returned `changed_claims: 0`;
- a verdict change returned `changed_claims: 1`;
- an added claim returned `changed_claims: 1`;
- one removal plus one verdict change returned `changed_claims: 2`;
- the Python `XanoSnapshotStore` adapter wrote snapshot `9` successfully.
- snapshots `10` and `11` used different claim wording but the same stable key
  and returned `changed_claims: 0`;
- snapshot `12` changed the verdict for that stable key and returned
  `changed_claims: 1`;
- two simultaneous writes produced snapshots `13` and `14`; snapshot `14`
  correctly named `13` as its predecessor and returned `changed_claims: 1`.
- a legacy-key migration sequence produced snapshots `18`–`20`: the first
  upgraded refresh established a zero-change baseline against snapshot `18`,
  then snapshot `20` correctly recorded the next verdict change.
- the published v5 sequence produced snapshots `36`–`39`: the repeated stable
  report returned `0`, a verdict change returned `1`, and an official-domain
  change returned `1`;
- snapshots `40`–`41` proved a valid empty v5 report establishes a baseline and
  a later added claim returns `1`.

The comparison key is not free-form model prose. VendorProof derives v5 identity
from a validated exact entity name and a deterministic requirement atom in the
immutable brief. It splits lists
and conjunctions so multiple products or requirements remain distinct, while
nested requirement phrases map to the same source atom. Claim text and search
queries must still mention the validated entity. Fact categories remain
descriptive metadata. The verified domain is excluded from persistent identity
but a domain change is counted as a conflict signal. Older schemas receive one
baseline refresh through the
explicit report-level `comparison_schema` marker.

Snapshots `33`–`35` provided the v4 migration acceptance: a v3 snapshot
was followed by a zero-change v4 baseline, then the next verdict change returned
exactly one.

No credential value or procurement data beyond deliberately synthetic smoke
records is included in the repository.
