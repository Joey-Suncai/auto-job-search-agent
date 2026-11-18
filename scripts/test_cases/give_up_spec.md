# Spec: "Give up" button of the dashboard's "Waiting for you" table (JSA-406)

Joey gives up a task a company asked of him after he applied (an assessment, a form, an interview). It is recorded on the
application's tracker row as status `Declined by Joey`; nothing is sent to the company.

## decline(row, give_up, today) → (new_row, error)
`row` = one tracker row (dict with at least job_id, company, status; maybe action_needed, action_deadline, action_done,
next_step, updated, declined). `today` = ISO date string. The input dict is never modified. "No open action" = action_needed
missing, empty / only spaces, or exactly "等结果".
- give_up = true:
  - status is already "Declined by Joey" → (unchanged row, "already declined").
  - no open action → (unchanged row, "no open action on this row").
  - else new row: `declined` = {"on": today, "status": <old status>, "action": <action_needed trimmed>,
    "deadline": <old action_deadline or "">, "next_step": <old next_step or "">}; status = "Declined by Joey";
    action_needed = ""; action_deadline = ""; next_step = "Declined by Joey " + today; updated = today. error = null.
    Nothing else changes (action_done history stays as it was).
- give_up = false (undo):
  - status is not "Declined by Joey" → (unchanged row, "not declined").
  - no `declined` key → (unchanged row, "nothing to undo").
  - else status, action_needed, action_deadline, next_step are restored from `declined` (status, action, deadline,
    next_step); the `declined` key is removed; updated = today. error = null.

## validate(method, path, headers, body) for path "/decline" → (code, payload)
Same server checks as /action, in this order: Host header must be localhost or 127.0.0.1 (optional :port) else 421;
path (query string ignored) must be one of /pref, /action, /apply, /decline else 404; method must be POST else 405;
Origin absent, "null", or http://localhost[:port] / http://127.0.0.1[:port] else 403; header x-jsa-pref exactly "1" else 403;
content-type starts with application/json (case-insensitive) else 415; body > 1024 bytes → 413; not JSON → 400.
For /decline: the JSON must be an object with exactly the keys job_id and give_up, else 400; job_id a string "J" + 4 to 6
digits, else 400; give_up a JSON boolean (not 0/1, not "true"), else 400.
Success → (200, {"route": "/decline", "job_id": <job_id>, "give_up": <give_up>}). Headers have lower-case keys.

## joey_todo.tracker_actions(apps, today)
A tracker row whose status is "Declined by Joey" yields no to-do row, even when it still has an action_needed.

## echo_funnel.records(apps, emails, jobs)
Each record gets `declined` = 1 when the application's status is "Declined by Joey", else 0. Such an application is still
counted as sent (it keeps its other fields).
