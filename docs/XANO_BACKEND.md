# Xano backend contract

VendorProof uses Xano as the system of record for procurement briefs and their
evidence snapshots. The frontend never receives Xano credentials.

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
  "brief": "A bounded procurement brief",
  "report": {"generated_at": "...", "overall_action": "review", "claims": []}
}
```

Behavior:

1. Normalize and hash the brief.
2. Find or create its `briefs` record.
3. Load the newest prior snapshot for that brief.
4. Compare claim verdicts and count changes.
5. Save the complete new snapshot.
6. Return only the receipt below.

Response:

```json
{
  "snapshot_id": "42",
  "previous_snapshot_id": "37",
  "changed_claims": 2
}
```

The production endpoint is configured through `XANO_SNAPSHOT_ENDPOINT`. An
optional server-to-server bearer credential is stored only as
`XANO_API_TOKEN` in the deployment secret store.
