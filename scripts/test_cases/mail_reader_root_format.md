Return {"cases": [...]}; each case:
{"name": "...", "fn": "classify" | "match" | "apply_mail" | "health", "spec": "<quoted spec sentence>", "ambiguous": false,
 "args": {...}, "expect": ...}

fn "classify": args {"subject", "body"}; expect = "<type>" or null.
fn "match": args {"apps": [{job_id, company, title, status, applied_on}], "sender", "subject", "body", "date"};
  expect = "<job_id>" or null.
fn "apply_mail": args {"apps": [...], "emails": [stored rows], "m": {id, date, sender, subject, body, bulk},
  "reader": "raise:<error text>" | <verdict {is_job_related, job_id, company_job_ids, type, summary, action_needed,
  deadline, confidence, reason}> | null}
  expect (only the keys you give are checked) = {"returns": "none"|"row"|"unmatched",
   "status": {"<job_id>": "<status after>"}, "applied_on": {"<job_id>": "<date>"},
   "stored": {"<message id>": "<type>" | "absent"}, "stored_job": {"<message id>": "<job_id or empty>"},
   "rules_type": "<rules_type of the stored row of m>"}
  A stored row that a rules stage move created carries "stage_before" (e.g. "Applied").
fn "health": args {"state": {...}, "fails": ["<error text>", ...], "oks": int, "now": "<ISO datetime with offset>"};
  expect = {"ok": bool, "alert": bool, "cause_in_body": "credit"|"auth"|"error"|null}
  (cause_in_body: which cause the alert body names; null when no alert.) State keys you may use: ok, since, fails, alerted
  ("alerted" = the `since` of an outage already alerted).
