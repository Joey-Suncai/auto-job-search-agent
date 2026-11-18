A JSON array of about 30 cases. Each case is one object with "name" (str), "fn" (one of answer_of, pending, line,
recheck, push_line, due_note), "spec_quote" (str) and:
- answer_of: "sheet": {...}, "q": {...}, "expect": <value or null>
- pending: "sheet": <any JSON>, "handled": [names] or null, "expect": [ids]
- line: "sheet": <any JSON>, "ids": [ids], "expect_exact": str (only when ids empty) or "expect_prefix": str
- recheck: "recs": [...], "answers_by_label": {label: result dict} (the stub answer() returns, for each unique item,
  the result for its label, or {"status": "unknown"} when absent), "today": "2026-11-07", "expect_changed": [ids],
  "expect_recs": [...full records after...], "expect_calls": 0 or 1, "expect_items": int (unique items passed, when called)
- push_line: "summary": {...} or null, "expect": null or {"title": str, "body_contains": [str, ...]}
- due_note: "mode": str, "status_line": str, "expect_empty": bool, "expect_prefix": str|null, "contains": [str],
  "not_contains": [str]
Cover: about 5 answer_of, 6 pending, 4 line, 9 recheck (dedupe, rule uncertain, ask/uncertain flags, not required,
status not ok, needs with files/tasks, nothing to check → 0 calls, partial changes), 3 push_line, 4 due_note.
