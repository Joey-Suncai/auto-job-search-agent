# learn.py — daily proposals and metric card — spec (JSA-191, self-optimisation step 6, 2026-11-17)

Every day `learn.py` reads what the runners recorded and writes a ledger of improvement PROPOSALS (it only proposes: it never
changes an answer, a rule or a saved answer) and a metric card. Three pure functions are specified here.

## findings(results, fields, wrong, replay, now, days=14) -> list of {"type", "key", "at", "evidence"}
All inputs cover the last `days` days only (rows older than `now - days` are ignored; a row without a readable `at` is ignored).
`results` = [{"at": ISO, "folder": str, "ats": str, "status": str, "problems": [str], "stopped_at": str|null, "mode": str|null}],
`fields` = [{"at": ISO, "folder": str, "ats": str, "question": str, "planned": str|null, "ok": bool}],
`wrong` = [{"folder": str, "field": str, "note": str, "found": "YYYY-MM-DD"}], `replay` = [{"folder": str, "question": str, "old": str, "new": str, "submitted": bool, "reason": str|null}].
A finding's `key` is its stable identity text, `at` the ISO time of its newest evidence, `evidence` a sorted list of the folders involved.
Three types:
- **fact**: a question the rules could not answer (a field row with `ok` false and `planned` null or empty) that appears in at least TWO different folders. key = the question lowercased, punctuation removed, spaces collapsed. Evidence = the folders. A question seen in one folder only is not a finding.
- **rule**: (a) every `wrong` row → key = "wrong:" + its field normalised as above; evidence = [its folder]; `at` = found date at 00:00 UTC; (b) every `replay` row with `submitted` true and an empty / null `reason` → key = "replay:" + question normalised; evidence = [folder]; `at` = now. Rows of the same key merge into one finding (evidence = all folders).
- **runner**: results rows (dry runs included) whose status is one of blocked, handoff, failed, login-timeout, unconfirmed and that have at least one problem text or a stopped_at. Signature = ats + "|" + (stopped_at or "") + "|" + first problem text lowercased with digits removed, quoted text (single or double quotes) removed, spaces collapsed, cut to 60 characters. A signature seen in at least TWO different folders is a finding, key = the signature.
The result is sorted by key.

## update_ledger(ledger, found, now) -> ledger
`ledger` = [{"id", "type", "key", "status", "first_seen", "last_seen", "evidence", "fixed_by", "fixed_at", "reopened"}]; `found` = the findings; `now` ISO.
The id of a finding is type + ":" + the first 8 hex characters of the SHA-1 of its key (UTF-8).
- A finding with no ledger entry → a new entry: status "open", first_seen = last_seen = now, evidence as found, fixed_by null, fixed_at null, reopened 0.
- A finding whose entry is "open" or "fixing" → last_seen = now, evidence = the union (sorted); status unchanged.
- A finding whose entry is "fixed" and whose `at` is later than the entry's `fixed_at` → the entry is REOPENED: status "open", reopened + 1, last_seen = now, evidence union; fixed_by / fixed_at are kept for the record.
- A finding whose entry is "fixed" and whose `at` is not later than `fixed_at` → no change (the old evidence of a problem already fixed).
- A finding whose entry is "wontfix" → no change.
- Ledger entries without a finding today are kept unchanged. Entries stay in their original order, new ones appended in key order.

## platform_metrics(results, now, days=7) -> {ats: {"runs", "submitted", "clean_first_rate", "runs_per_submit", "joey_per_submit"}}
Rows of the last `days` days. Per ats, over its real runs (rows whose mode is not "dry-run" plus dry runs: all rows count as runs):
- runs = number of rows; submitted = number of distinct folders with a "submitted" row.
- clean_first_rate = the share of distinct folders whose FIRST row (earliest `at`) has no problems and a status of "submitted" or "dry-run" (a number between 0 and 1, rounded to 2 decimals; null when there are no folders).
- runs_per_submit = runs / submitted rounded to 2 decimals (null when submitted is 0).
- joey_per_submit = the number of distinct folders with at least one row whose status is needs-user, captcha, login-timeout, unconfirmed or handoff, divided by submitted, rounded to 2 decimals (null when submitted is 0).
