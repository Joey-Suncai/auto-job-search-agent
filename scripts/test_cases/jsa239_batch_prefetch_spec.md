# batch_apply prepare reads the form prefetch (JSA-239)

Every morning the form prefetch saves one record per job (read on `read_at`, a date). A record has `status`:
"ok" (form read), "closed" (the posting is gone / the application page is closed), "restricted" (the form limits who may
apply, e.g. citizens only — the candidate cannot apply), "error" (not readable). An "ok" record has `needs` = how many
questions / files / tasks the candidate still has to deal with (0 = ready), or no `needs` at all.

Before a batch is prepared (`prepare`), every job of the batch is looked up in the prefetch records by its job id:
- A record that is FRESH (read_at at most 5 days before today, inclusive: read 5 days ago is fresh, 6 days ago is stale) and has
  status "closed" or "restricted" → the job is SKIPPED before any preparation work: its row gets the status
  "skipped: closed (prefetch YYYY-MM-DD)" or "skipped: restricted (prefetch YYYY-MM-DD)" with that read_at date, ready false.
  (When both closed and a restriction apply the record status decides.)
- A fresh "ok" record → the job is prepared as before; its row additionally shows `prefetch_left` = the record's `needs`
  (a number; a missing `needs` shows nothing) so the report says how many questions are still open.
- A STALE record of any status, an "error" record, or no record → no change: the job is prepared as before, no extra fields.
- A record whose read_at is missing or not a date is treated as stale.
Job ids that are not in the records are never an error. The skipped jobs do not count against the batch size limit.
The form is still re-read live before submitting; the prefetch only saves preparing work.
