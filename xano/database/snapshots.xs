table snapshots {
  auth = false

  schema {
    int id
    int brief_id {
      table = "briefs"
    }

    timestamp generated_at
    text overall_action
    json report_json
    int changed_claims
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "brief_id"}]}
  ]
}
