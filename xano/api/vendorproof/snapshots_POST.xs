// Create a new snapshot for a procurement brief
query snapshots verb=POST {
  api_group = "vendorproof"

  input {
    // Shared service credential supplied only by Cloud Run
    text api_token

    // The procurement brief text
    text brief filters=max:12000

    // The generated report object
    object report {
      schema {
        // Stable comparison identity schema used by every claim in this report
        text comparison_schema

        // ISO timestamp of report generation
        timestamp generated_at

        // Summary action recommendation
        text overall_action

        // Array of claim objects with nested candidate and assessment
        json[] claims

        // Optional warning when a generated check could not be mapped safely
        text extraction_warning?
      }
    }
  }

  stack {
    // Require the private Cloud Run service token before any processing
    precondition ($input.api_token == $env.vendorproof_api_token) {
      error_type = "accessdenied"
      error = "Unauthorized."
    }

    // Validate brief is non-empty after trimming
    precondition (($input.brief|trim) != "") {
      error_type = "inputerror"
      error = "brief must be a non-empty string"
    }

    // Normalize brief: trim outer whitespace and normalize line endings to LF
    var $normalized_brief {
      value = ($input.brief|trim)|replace:"\r\n":"\n"|replace:"\r":"\n"
    }

    // Compute deterministic SHA-256 brief_hash
    var $brief_hash {
      value = $normalized_brief|sha256
    }

    // Define result variable to be populated within the transaction
    var $result {
      value = null
    }

    db.transaction {
      stack {
        // Find or create the briefs record by brief_hash and update brief_text and updated_at
        db.add_or_edit briefs {
          field_name = "brief_hash"
          field_value = $brief_hash
          data = {
            brief_hash: $brief_hash
            brief_text: $normalized_brief
            updated_at: now
          }
        } as $brief_record

        // Serialize concurrent requests for the same brief before reading its predecessor.
        db.query briefs {
          lock = true
          where = $db.briefs.id == $brief_record.id
          return = {type: "single"}
        } as $_

        // Load the newest previous snapshot for that brief
        db.query snapshots {
          where = $db.snapshots.brief_id == $brief_record.id
          sort = {id: "desc"}
          return = {type: "single"}
        } as $previous_snapshot

        // Compare current versus previous claim verdicts
        var $changed_claims {
          value = 0
        }

        // Legacy snapshots predate an explicit comparison schema. The first upgraded refresh
        // establishes a clean baseline instead of reporting every claim twice.
        var $legacy_previous {
          value = false
        }

        conditional {
          if ($previous_snapshot != null) {
            conditional {
              if (($previous_snapshot.report_json|get:"comparison_schema") != "v5") {
                var.update $legacy_previous {
                  value = true
                }
              }
            }

            foreach ($previous_snapshot.report_json.claims) {
              each as $previous_claim {
                var $p_key {
                  value = $previous_claim
                    |get:"candidate":{}
                    |get:"comparison_key"
                }

                conditional {
                  if (($p_key == null) || (($p_key|starts_with:"v5_") == false)) {
                    var.update $legacy_previous {
                      value = true
                    }
                  }
                }
              }
            }

            conditional {
              if ($legacy_previous == false) {
                // Count added claims and verdict changes.
                foreach ($input.report.claims) {
                  each as $current_claim {
                    var $c_key {
                      value = $current_claim
                        |get:"candidate":{}
                        |get:"comparison_key"
                    }

                    var $matched_previous {
                      value = false
                    }

                    foreach ($previous_snapshot.report_json.claims) {
                      each as $previous_claim {
                        var $p_key {
                          value = $previous_claim
                            |get:"candidate":{}
                            |get:"comparison_key"
                        }

                        conditional {
                          if (($c_key != null) && ($c_key == $p_key)) {
                            var.update $matched_previous {
                              value = true
                            }

                            var $c_domain {
                              value = $current_claim
                                |get:"candidate":{}
                                |get:"entity_domain"
                            }

                            var $p_domain {
                              value = $previous_claim
                                |get:"candidate":{}
                                |get:"entity_domain"
                            }

                            var $c_verdict {
                              value = $current_claim
                                |get:"assessment":{}
                                |get:"verdict"
                            }

                            var $p_verdict {
                              value = $previous_claim
                                |get:"assessment":{}
                                |get:"verdict"
                            }

                            conditional {
                              if (($c_domain == null) || ($p_domain == null) || ($c_domain != $p_domain)) {
                                var.update $changed_claims {
                                  value = $changed_claims + 1
                                }
                              }

                              elseif ($c_verdict != $p_verdict) {
                                var.update $changed_claims {
                                  value = $changed_claims + 1
                                }
                              }
                            }
                          }
                        }
                      }
                    }

                    conditional {
                      if ($matched_previous == false) {
                        var.update $changed_claims {
                          value = $changed_claims + 1
                        }
                      }
                    }
                  }
                }

                // Count claims that were removed.
                foreach ($previous_snapshot.report_json.claims) {
                  each as $previous_claim {
                    var $p_key {
                      value = $previous_claim
                        |get:"candidate":{}
                        |get:"comparison_key"
                    }

                    var $matched_current {
                      value = false
                    }

                    foreach ($input.report.claims) {
                      each as $current_claim {
                        var $c_key {
                          value = $current_claim
                            |get:"candidate":{}
                            |get:"comparison_key"
                        }

                        conditional {
                          if (($p_key != null) && ($p_key == $c_key)) {
                            var.update $matched_current {
                              value = true
                            }
                          }
                        }
                      }
                    }

                    conditional {
                      if ($matched_current == false) {
                        var.update $changed_claims {
                          value = $changed_claims + 1
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }

        // Save the complete report object unchanged as report_json
        db.add snapshots {
          data = {
            brief_id      : $brief_record.id
            generated_at  : $input.report.generated_at
            overall_action: $input.report.overall_action
            report_json   : $input.report
            changed_claims: $changed_claims
          }
        } as $new_snapshot

        var $prev_id {
          value = null
        }

        conditional {
          if ($previous_snapshot != null) {
            var.update $prev_id {
              value = $previous_snapshot.id|to_text
            }
          }
        }

        var.update $result {
          value = {
            snapshot_id         : $new_snapshot.id|to_text
            previous_snapshot_id: $prev_id
            changed_claims      : $changed_claims
          }
        }
      }
    }
  }

  response = $result
}
