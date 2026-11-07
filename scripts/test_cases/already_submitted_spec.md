# Never submit the same application twice (JSA-145, 2026-11-04)

`already_submitted(folder, results_path)` reads data/runner/results.jsonl (one JSON object per line) and returns True when
any line has `"folder"` equal to the folder's base name (the last path part; a trailing slash is ignored) and
`"status": "submitted"` — whoever submitted it (`"by": "runner"`, `"by": "joey"`, or no `by`). Lines with another status
(dry-run, blocked, captcha, unconfirmed, needs-user) do not count. Invalid JSON lines are skipped. A missing results file →
False. The folder name must match exactly (no prefix / substring match: "2026-11-04_Acme_Intern" is not
"2026-11-04_Acme_Intern_2").
