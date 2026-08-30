table briefs {
  auth = false

  schema {
    int id
    text brief_hash
    text brief_text
    timestamp created_at?=now
    timestamp updated_at?
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "brief_hash"}]}
  ]
}
