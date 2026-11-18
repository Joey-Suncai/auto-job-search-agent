# receipt_confirm — spec (JSA-193 step 8, 2026-11-17)

After a Submit the page sometimes shows no confirmation. The runner then records the application as `unconfirmed`
(one line in results.jsonl) and Joey checks Gmail by hand. A daily job now confirms such applications by itself from the
company's application-received e-mail, and flags the ones that stay without a receipt for 48 hours.

## open_unconfirmed(rows, now, days=7) -> list of rows
`rows` are the lines of results.jsonl in file order, each `{"at": ISO-8601 time with offset, "folder": str, "status": str,
"mode": optional str, "url": optional, "ats": optional}`. `now` is a timezone-aware datetime.
A folder is open when its LAST row (the last one in the list for that folder) has status `unconfirmed`, that row's mode is not
`dry-run`, and its `at` is at most `days` days before `now`. A later row for the same folder with status `submitted` (or
`already-submitted`) closes it; a later dry-run row or a later `blocked` / `needs-user` row does NOT reopen or close it
(rows with mode `dry-run` are ignored entirely). Return the last unconfirmed row of each open folder, oldest first.
A row without `at` or with an unreadable `at` is ignored.

## receipt_decision(at, subject, now, hours=48) -> "confirm" | "wait" | "joey"
`at` is the ISO time of the unconfirmed row, `subject` the subject of the company e-mail found for it (None or blank when there is none).
- a non-blank `subject` → "confirm" (whatever the age);
- otherwise, when `now` is at least `hours` hours after `at` → "joey" (no receipt in 48 hours: Joey checks the site);
- otherwise → "wait".
