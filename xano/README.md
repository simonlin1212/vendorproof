# VendorProof Xano backend

This directory mirrors the XanoScript currently published in the VendorProof
workspace. It makes the sponsor integration reviewable alongside the Python
orchestrator without including workspace credentials.

Apply the files in this order:

1. `database/briefs.xs`
2. `database/snapshots.xs`
3. `api/vendorproof/api_group.xs`
4. `api/vendorproof/snapshots_POST.xs`

Create a private workspace environment variable named
`vendorproof_api_token`. Cloud Run sends the matching value as `api_token` over
HTTPS. Do not put the value in this repository or expose it to the browser.

The production workspace and live receipt evidence are recorded in
[`../docs/XANO_BACKEND.md`](../docs/XANO_BACKEND.md).
