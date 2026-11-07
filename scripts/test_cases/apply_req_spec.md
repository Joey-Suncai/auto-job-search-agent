# Dashboard Apply requests — spec (2026-11-05, JSA-179)

## skip_names(text) → [str]
Text of a skip-list file → the lower-case company names: for each line, strip it; skip empty lines and lines starting
with "#"; the name is the part before the first "|", stripped, lower-cased; empty names dropped. Order kept.

## can_queue(job, applied_ids, skip, runner) → [bool, reason]
job: a dict with id, company, elig, apply_req (any may be missing). applied_ids: list of job ids already in the tracker.
skip: lower-case company names. runner: {"platform": str, "runner": "ready"|"testing"|"none"|"unknown"}.
Checks in this order; the first that fails gives [false, <non-empty reason>]:
1. elig must not be "不可投", "已关闭" or "重复" (可投, 待核实, empty or missing are fine);
2. job id must not be in applied_ids;
3. apply_req must not be "queued", "applying", "needs-you" or "submitted" ("cancelled" or missing is fine);
4. the company (stripped, lower-cased) must not be in skip;
5. the runner's platform must not be "tiktok".
Any runner status is fine otherwise. All pass → [true, ""]. (Only the boolean is checked by the cases, plus that a
refusal has a non-empty reason.)

## apply_mode(job, runner) → "runner" | "verify-first" | "by-hand"
"verify-first" when elig is "待核实", empty or missing (whatever the runner); else "runner" when runner is "ready", or
"testing" on a platform other than "tiktok"; else "by-hand".

## set_fields(job, status, now, note="", by="") → job
status must be one of queued, applying, submitted, needs-you, cancelled (else an error). Returns a NEW dict (the input is
not changed) with apply_req = status, apply_req_at = now; apply_req_note = note when note is non-empty, otherwise the
key is removed; apply_req_by = by when by is non-empty, otherwise any existing apply_req_by is kept. Other keys unchanged.

## queued(rows) → [[apply_req_at, id, company, title]]
Rows whose apply_req is exactly "queued", sorted by apply_req_at (as text), then id; missing company / title → "",
missing apply_req_at → "".

## validate(method, path, headers, body) for the /apply route of the local server
headers have lower-case keys; body is the request body text. A valid request: method POST, path "/apply" (a query
string is ignored), host "127.0.0.1" or "localhost" with any port or none (the server binds 127.0.0.1:8766 only; the host check is against DNS rebinding), origin missing or "null" or http://localhost /
http://127.0.0.1 (any port), header x-jsa-pref "1", content-type starting with "application/json", body ≤ 1024 bytes,
body = a JSON object with exactly the keys job_id and confirm, job_id = "J" + 4–6 digits, confirm = true (the boolean).
→ [200, {"route": "/apply", "job_id": <id>}]. Errors: bad host 421; unknown path 404; not POST 405; bad origin 403;
missing header 403; wrong content type 415; body too large 413; not JSON 400; wrong keys / bad job_id / confirm not
true 400. Only the status code is checked by the cases.
