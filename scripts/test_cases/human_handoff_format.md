Return {"cases": [...]}. Each case:
{"name": "unique_snake_case", "fn": "company" | "message" | "pending" | "summary", "args": {...}, "expect": ..., "spec": "quoted sentence"}
- company: args {"folder": str}; expect = the exact returned string.
- message: args {"folder": str, "checks": [...], "parked": true|false}; expect = {"title": exact title, "body_lines": [exact full list of body lines]}.
- pending: args {"rows": [...]}; expect = list of the folder names returned, in order.
- summary: args {"rows": [...]}; expect = null, or {"title": exact title, "body_contains": [substrings that must appear], "body_not_contains": [substrings that must not appear]}.
Write 24 cases, at least 4 per function. For message lines, follow the spec exactly (the last line: write only one that the spec fully determines — if it does not, put the line as "<<LAST>>" and the harness checks it contains "job Chrome" and the parked phrase).
