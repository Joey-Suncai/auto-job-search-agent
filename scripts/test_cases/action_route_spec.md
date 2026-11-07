# Tracker "Done" button — spec (JSA-125)

## mark(row, done, today) → (new_row, error)
`row` is one tracker row (a dict with at least job_id, company, status, and maybe action_needed, action_done, updated).
`today` is an ISO date string. The input dict is never modified.
- "No open action" = action_needed missing, empty / only spaces, or exactly "等结果" (after trimming).
- done = true:
  - no open action → return (the unchanged row, "no open action on this row").
  - else: append {"on": today, "action": <action_needed trimmed>} to the row's `action_done` list (create it if missing;
    keep older entries in order), set action_needed = "", updated = today. error = null.
- done = false (undo):
  - no `action_done` list or an empty one → (unchanged row, "nothing to undo").
  - the row has an open action → (unchanged row, "the row has a new action since; nothing undone").
  - else remove the LAST entry of action_done and put its "action" back into action_needed; updated = today; if the
    list is now empty, the `action_done` key is removed entirely. error = null.
- No other field changes.

## validate(method, path, headers, body) for path "/action" → (code, payload)
Same server checks as /pref, in this order: Host header must be localhost or 127.0.0.1 (optional :port) else 421;
path (query string ignored) must be /pref or /action else 404; method must be POST else 405; Origin header absent,
"null", or http://localhost[:port] / http://127.0.0.1[:port] else 403; header x-jsa-pref must be exactly "1" else 403;
content-type must start with application/json (case-insensitive) else 415; body > 1024 bytes → 413; body not JSON → 400.
For /action: the JSON must be an object with exactly the keys job_id and done, else 400; job_id must be a string
"J" + 4 to 6 digits, else 400; done must be a JSON boolean (not 0/1, not "true"), else 400.
Success → (200, {"route": "/action", "job_id": <job_id>, "done": <done>}).
Headers are given with lower-case keys.
